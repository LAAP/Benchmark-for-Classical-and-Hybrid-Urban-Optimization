from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .formulation import oriented_dims
from .models import Placement, Scenario, Solution

VIOLATION_KEYS = [
    "overlap_violations",
    "boundary_violations",
    "assignment_violations",
    "activation_consistency_violations",
    "density_violations",
    "other_violations",
]


def overlaps_3d(a: Placement, b: Placement, aw: int, ad: int, bw: int, bd: int) -> bool:
    if a.sector_id != b.sector_id:
        return False
    ax2, ay2, az2 = a.x + aw, a.y + ad, a.z + a.height
    bx2, by2, bz2 = b.x + bw, b.y + bd, b.z + b.height
    separated = (ax2 <= b.x) or (bx2 <= a.x) or (ay2 <= b.y) or (by2 <= a.y) or (az2 <= b.z) or (bz2 <= a.z)
    return not separated


def evaluate_solution(scenario: Scenario, placements: List[Placement]) -> Solution:
    sector_map = {s.id: s for s in scenario.sectors}
    block_map = {b.id: b for b in scenario.blocks}
    violations: List[str] = []
    active = set()

    seen = set()
    for p in placements:
        if p.block_id in seen:
            violations.append(f"duplicate_assignment:{p.block_id}")
        seen.add(p.block_id)
        active.add(p.sector_id)

        if p.sector_id not in sector_map:
            violations.append(f"unknown_sector:{p.sector_id}")
            continue
        if p.block_id not in block_map:
            violations.append(f"unknown_block:{p.block_id}")
            continue

        sec = sector_map[p.sector_id]
        blk = block_map[p.block_id]
        w, d = oriented_dims(blk, p.orientation)
        if p.x < 0 or p.y < 0 or p.z < 0:
            violations.append(f"negative_position:{p.block_id}")
        if p.x + w > sec.width or p.y + d > sec.depth or p.z + p.height > sec.max_height:
            violations.append(f"out_of_bounds:{p.block_id}")
        if not (blk.min_height <= p.height <= blk.max_height):
            violations.append(f"height_invalid:{p.block_id}")

    for blk in scenario.blocks:
        if blk.id not in seen:
            violations.append(f"missing_assignment:{blk.id}")

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            bi = block_map.get(placements[i].block_id)
            bj = block_map.get(placements[j].block_id)
            if not bi or not bj:
                continue
            wi, di = oriented_dims(bi, placements[i].orientation)
            wj, dj = oriented_dims(bj, placements[j].orientation)
            if overlaps_3d(placements[i], placements[j], wi, di, wj, dj):
                violations.append(f"overlap:{placements[i].block_id}:{placements[j].block_id}")

    by_sector = defaultdict(list)
    for p in placements:
        by_sector[p.sector_id].append(p)
    skyline = 0.0
    for sec_id, ps in by_sector.items():
        if sec_id in sector_map:
            skyline += max(p.z + p.height for p in ps) / max(1, sector_map[sec_id].max_height)

    # Compactness proxy: reward fewer sectors and short pairwise sector spread.
    compactness_penalty = float(len(active))
    density_total = sum(
        block_map[p.block_id].density_weight * p.height for p in placements if p.block_id in block_map
    )
    min_total = sum(b.density_weight * b.min_height for b in scenario.blocks)
    max_total = sum(b.density_weight * b.max_height for b in scenario.blocks)
    span = max(1e-9, max_total - min_total)
    density_norm = (density_total - min_total) / span
    density_norm = max(0.0, min(1.0, density_norm))
    density_dev = abs(density_norm - scenario.density_target)
    density_tol = 0.20
    if density_dev > density_tol:
        violations.append(f"density_deviation_excess:{density_dev:.6f}")

    compatibility_penalty = 0.0
    for sec_id, ps in by_sector.items():
        for i in range(len(ps)):
            bi = block_map.get(ps[i].block_id)
            if not bi:
                continue
            for j in range(i + 1, len(ps)):
                bj = block_map.get(ps[j].block_id)
                if not bj:
                    continue
                if bi.block_type != bj.block_type:
                    compatibility_penalty += scenario.compatibility_strength * 0.05

    w = scenario.objective_weights
    objective = (
        w.active_sectors * len(active)
        + w.skyline_height * skyline
        + w.compactness * compactness_penalty
        + w.density_deviation * density_dev
        + w.compatibility * compatibility_penalty
    )

    breakdown = {k: 0 for k in VIOLATION_KEYS}
    for v in violations:
        if v.startswith("overlap:"):
            breakdown["overlap_violations"] += 1
        elif v.startswith("out_of_bounds:") or v.startswith("negative_position:") or v.startswith("height_invalid:"):
            breakdown["boundary_violations"] += 1
        elif v.startswith("missing_assignment:") or v.startswith("duplicate_assignment:") or v.startswith("unknown_block:"):
            breakdown["assignment_violations"] += 1
        elif v.startswith("unknown_sector:"):
            breakdown["activation_consistency_violations"] += 1
        elif v.startswith("density_"):
            breakdown["density_violations"] += 1
        else:
            breakdown["other_violations"] += 1

    return Solution(
        placements=placements,
        active_sectors=sorted(active),
        objective=float(objective),
        feasible=len(violations) == 0,
        violations=violations,
        violation_breakdown=breakdown,
        density_metrics={
            "density_total": float(density_total),
            "density_min_total": float(min_total),
            "density_max_total": float(max_total),
            "density_norm": float(density_norm),
            "density_target": float(scenario.density_target),
            "density_gap": float(density_dev),
            "density_tolerance": float(density_tol),
        },
        exact_optimum=False,
    )


def solution_to_dict(solution: Solution) -> Dict:
    return solution.model_dump()
