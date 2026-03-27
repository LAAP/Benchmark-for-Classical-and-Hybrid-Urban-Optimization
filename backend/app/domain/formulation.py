from __future__ import annotations

"""
Shared discrete candidate formulation used by both CP-SAT and QUBO paths.

This module is intentionally central for benchmark hygiene:
- candidate universe definition (including strict parity variants),
- conflict edge construction,
- objective term proxy used by both solver families.
"""

from dataclasses import dataclass
from itertools import combinations, cycle
from typing import Dict, List, Tuple

from app.domain.models import Block, Scenario
def parity_mode_terms(strict: bool) -> Dict[str, List[str]]:
    if strict:
        return {
            "included_variables": ["candidate_selection", "sector_activation"],
            "included_constraints": ["exactly_one_assignment", "pairwise_non_overlap", "boundary_by_construction"],
            "included_objective_terms": ["active_sectors", "skyline_height", "compactness", "density_deviation"],
            "excluded_terms": ["compatibility", "accessibility"],
        }
    return {
        "included_variables": ["candidate_selection", "sector_activation"],
        "included_constraints": ["exactly_one_assignment", "pairwise_non_overlap", "boundary_by_construction"],
        "included_objective_terms": ["active_sectors", "skyline_height", "compactness", "density_deviation", "compatibility_proxy"],
        "excluded_terms": ["accessibility"],
    }


@dataclass(frozen=True)
class CandidatePlacement:
    placement_id: str
    block_id: str
    sector_id: str
    orientation: int
    x: int
    y: int
    z: int
    height: int
    width: int
    depth: int


def oriented_dims(block: Block, orientation: int) -> Tuple[int, int]:
    return (block.depth, block.width) if orientation == 1 else (block.width, block.depth)


def _stride_heights(block: Block, stride_z: int) -> List[int]:
    return list(range(block.min_height, block.max_height + 1, max(1, stride_z)))


def _representative_heights(heights: List[int]) -> List[int]:
    """Up to 3 distinct stride heights: low, mid, high — preserves diversity under tight caps."""
    if len(heights) <= 3:
        return heights
    return [heights[0], heights[len(heights) // 2], heights[-1]]


def _iter_placements_for_fixed_height(
    block: Block,
    scenario: Scenario,
    h: int,
    orientation: int,
    sector,
    stride_xy: int,
    stride_z: int,
):
    w, d = oriented_dims(block, orientation)
    max_x = sector.width - w
    max_y = sector.depth - d
    max_z = sector.max_height - h
    if max_x < 0 or max_y < 0 or max_z < 0:
        return
    sx = max(1, stride_xy)
    sz = max(1, stride_z)
    for x in range(0, max_x + 1, sx):
        for y in range(0, max_y + 1, sx):
            for z in range(0, max_z + 1, sz):
                pid = f"p_{block.id}_{sector.id}_{orientation}_{x}_{y}_{z}_{h}"
                yield CandidatePlacement(
                    placement_id=pid,
                    block_id=block.id,
                    sector_id=sector.id,
                    orientation=orientation,
                    x=x,
                    y=y,
                    z=z,
                    height=h,
                    width=w,
                    depth=d,
                )


def _generate_candidates_strict_stratified(
    scenario: Scenario,
    block: Block,
    stride_xy: int,
    stride_z: int,
    cap: int,
    *,
    sector_balanced: bool = False,
) -> List[CandidatePlacement]:
    """
    Strict parity: split the per-block cap across multiple stride heights so density achievability
    does not collapse when the cap is exhausted at the first height only.
    """
    heights_all = _stride_heights(block, stride_z)
    if not heights_all:
        return []
    heights = _representative_heights(heights_all)
    n_h = len(heights)
    quota: Dict[int, int] = {}
    base, rem = divmod(cap, n_h)
    for i, h in enumerate(heights):
        quota[h] = base + (1 if i < rem else 0)

    out: List[CandidatePlacement] = []
    seen: set[Tuple[str, int, int, int, int, int]] = set()

    def _pkey(c: CandidatePlacement) -> Tuple[str, int, int, int, int, int]:
        return (c.sector_id, c.orientation, c.x, c.y, c.z, c.height)

    def _iter_balanced_for_height(hh: int):
        """
        Deterministic sector-balanced enumeration: cycle across (sector, orientation) pairs
        so the per-block cap does not saturate in the first sector if other sectors have
        reachable placements.
        """
        streams = []
        for s in scenario.sectors:
            for orientation in (0, 1):
                it = _iter_placements_for_fixed_height(block, scenario, hh, orientation, s, stride_xy, stride_z)
                if it is not None:
                    streams.append((s.id, orientation, iter(it)))
        if not streams:
            return
        idx = 0
        alive = len(streams)
        while alive > 0:
            sid, ori, it = streams[idx]
            try:
                c = next(it)
                yield c
                idx = (idx + 1) % len(streams)
            except StopIteration:
                streams.pop(idx)
                alive -= 1
                if streams:
                    idx %= len(streams)

    # Quota pass: try to reserve ~cap/n_h placements per representative height.
    for h in heights:
        need = quota[h]
        if need <= 0 or len(out) >= cap:
            continue
        got = 0
        if sector_balanced:
            it = _iter_balanced_for_height(h)
            if it is not None:
                for c in it:
                    if got >= need or len(out) >= cap:
                        break
                    k = _pkey(c)
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(c)
                    got += 1
        else:
            for s in scenario.sectors:
                for orientation in (0, 1):
                    if got >= need or len(out) >= cap:
                        break
                    for c in _iter_placements_for_fixed_height(block, scenario, h, orientation, s, stride_xy, stride_z):
                        if got >= need or len(out) >= cap:
                            break
                        k = _pkey(c)
                        if k in seen:
                            continue
                        seen.add(k)
                        out.append(c)
                        got += 1
                if got >= need or len(out) >= cap:
                    break

    # Top-up: fill remaining cap with any unseen (h,s,o) cells; round-robin heights.
    if len(out) < cap:
        h_cycle = cycle(heights)
        stall = 0
        max_stall = max(200, cap * len(heights) * 8)
        while len(out) < cap and stall < max_stall:
            h = next(h_cycle)
            before = len(out)
            if sector_balanced:
                it = _iter_balanced_for_height(h)
                if it is not None:
                    for c in it:
                        k = _pkey(c)
                        if k in seen:
                            continue
                        seen.add(k)
                        out.append(c)
                        if len(out) >= cap:
                            break
            else:
                for s in scenario.sectors:
                    for orientation in (0, 1):
                        for c in _iter_placements_for_fixed_height(block, scenario, h, orientation, s, stride_xy, stride_z):
                            k = _pkey(c)
                            if k in seen:
                                continue
                            seen.add(k)
                            out.append(c)
                            if len(out) >= cap:
                                break
                        if len(out) >= cap:
                            break
                    if len(out) >= cap:
                        break
            if len(out) == before:
                stall += 1
            else:
                stall = 0

    return out[:cap]


def generate_candidates(
    scenario: Scenario,
    stride_xy: int = 2,
    stride_z: int = 2,
    max_candidates_per_block: int = 160,
    strict_parity_mode: bool = False,
    *,
    sector_balanced: bool = False,
) -> Dict[str, List[CandidatePlacement]]:
    # Important benchmark assumption: both solvers must read from this same candidate map.
    # Any cap/stride/enumeration changes here directly affect comparability claims.
    candidates: Dict[str, List[CandidatePlacement]] = {b.id: [] for b in scenario.blocks}
    for b in scenario.blocks:
        if strict_parity_mode:
            candidates[b.id] = _generate_candidates_strict_stratified(
                scenario, b, stride_xy, stride_z, max_candidates_per_block, sector_balanced=sector_balanced
            )
            continue
        if sector_balanced:
            # Round-robin across (sector, orientation, height) streams to avoid saturating in the first sector.
            streams = []
            for s in scenario.sectors:
                for orientation in (0, 1):
                    w, d = oriented_dims(b, orientation)
                    for h in range(b.min_height, b.max_height + 1, max(1, stride_z)):
                        it = _iter_placements_for_fixed_height(b, scenario, h, orientation, s, stride_xy, stride_z)
                        if it is not None:
                            streams.append(iter(it))
            idx = 0
            while streams and len(candidates[b.id]) < max_candidates_per_block:
                it = streams[idx]
                try:
                    c = next(it)
                    candidates[b.id].append(c)
                    idx = (idx + 1) % len(streams)
                except StopIteration:
                    streams.pop(idx)
                    if streams:
                        idx %= len(streams)
        else:
            for s in scenario.sectors:
                for orientation in (0, 1):
                    w, d = oriented_dims(b, orientation)
                    for h in range(b.min_height, b.max_height + 1, max(1, stride_z)):
                        max_x = s.width - w
                        max_y = s.depth - d
                        max_z = s.max_height - h
                        if max_x < 0 or max_y < 0 or max_z < 0:
                            continue
                        for x in range(0, max_x + 1, max(1, stride_xy)):
                            for y in range(0, max_y + 1, max(1, stride_xy)):
                                for z in range(0, max_z + 1, max(1, stride_z)):
                                    pid = f"p_{b.id}_{s.id}_{orientation}_{x}_{y}_{z}_{h}"
                                    candidates[b.id].append(
                                        CandidatePlacement(
                                            placement_id=pid,
                                            block_id=b.id,
                                            sector_id=s.id,
                                            orientation=orientation,
                                            x=x,
                                            y=y,
                                            z=z,
                                            height=h,
                                            width=w,
                                            depth=d,
                                        )
                                    )
                                    if len(candidates[b.id]) >= max_candidates_per_block:
                                        break
                                if len(candidates[b.id]) >= max_candidates_per_block:
                                    break
                            if len(candidates[b.id]) >= max_candidates_per_block:
                                break
                        if len(candidates[b.id]) >= max_candidates_per_block:
                            break
                    if len(candidates[b.id]) >= max_candidates_per_block:
                        break
        candidates[b.id] = candidates[b.id][:max_candidates_per_block]
    return candidates


def overlap_3d(a: CandidatePlacement, b: CandidatePlacement) -> bool:
    if a.sector_id != b.sector_id:
        return False
    ax2, ay2, az2 = a.x + a.width, a.y + a.depth, a.z + a.height
    bx2, by2, bz2 = b.x + b.width, b.y + b.depth, b.z + b.height
    sep = (ax2 <= b.x) or (bx2 <= a.x) or (ay2 <= b.y) or (by2 <= a.y) or (az2 <= b.z) or (bz2 <= a.z)
    return not sep


def build_conflicts(candidates: Dict[str, List[CandidatePlacement]]) -> List[Tuple[str, str]]:
    all_candidates = [c for arr in candidates.values() for c in arr]
    conflicts: List[Tuple[str, str]] = []
    for a, b in combinations(all_candidates, 2):
        if a.block_id == b.block_id:
            conflicts.append((a.placement_id, b.placement_id))
            continue
        if overlap_3d(a, b):
            conflicts.append((a.placement_id, b.placement_id))
    return conflicts


def objective_cost(candidate: CandidatePlacement, scenario: Scenario, block_type: str, strict_parity_mode: bool = False) -> float:
    w = scenario.objective_weights
    sector = next(s for s in scenario.sectors if s.id == candidate.sector_id)
    skyline_norm = (candidate.z + candidate.height) / max(1.0, sector.max_height)
    compactness_proxy = (candidate.x + candidate.y + candidate.z) / max(1.0, sector.width + sector.depth + sector.max_height)
    density_dev_proxy = abs(skyline_norm - scenario.density_target)
    # Active-sector and accessibility are encoded as global terms in classical, approximated here.
    base = (
        w.skyline_height * skyline_norm
        + w.compactness * compactness_proxy
        + w.density_deviation * density_dev_proxy
    )
    if strict_parity_mode:
        return base
    return base + (0.01 if block_type == "green" else 0.0)
