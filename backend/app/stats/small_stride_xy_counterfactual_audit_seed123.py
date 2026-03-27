from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from app.domain.density_diagnostics import attach_benchmark_hygiene_metadata, density_achievability_report
from app.domain.formulation import build_conflicts, generate_candidates
from app.domain.instance_diagnostics import candidate_grid_params
from app.domain.models import ObjectiveWeights, SolverRunConfig
from app.domain.scenario_generator import generate_scenario


def _counts_per_sector(cand_map) -> Dict[str, int]:
    c = Counter()
    for arr in cand_map.values():
        for p in arr:
            c[p.sector_id] += 1
    return dict(sorted(c.items(), key=lambda kv: kv[0]))


def _block_summaries(scenario, cand_map, cap: int) -> List[Dict[str, Any]]:
    out = []
    for b in scenario.blocks:
        arr = cand_map[b.id]
        heights = sorted({int(p.height) for p in arr})
        secs = sorted({str(p.sector_id) for p in arr})
        out.append(
            {
                "block_id": str(b.id),
                "candidate_count": int(len(arr)),
                "cap": int(cap),
                "cap_hit": bool(len(arr) >= cap),
                "sectors_represented": secs,
                "unique_height_count": int(len(heights)),
                "height_min": int(heights[0]) if heights else None,
                "height_max": int(heights[-1]) if heights else None,
            }
        )
    return out


def _conflict_summary(cand_map) -> Dict[str, Any]:
    conflicts = build_conflicts(cand_map)
    total_candidates = sum(len(v) for v in cand_map.values())
    max_pairs = max(0, total_candidates * (total_candidates - 1) // 2)
    pid_to_block = {}
    for bid, arr in cand_map.items():
        for c in arr:
            pid_to_block[c.placement_id] = bid
    inter_block = sum(1 for a, b in conflicts if pid_to_block.get(a) != pid_to_block.get(b))
    intra_excl = sum(len(cand_map[bid]) * (len(cand_map[bid]) - 1) // 2 for bid in cand_map)
    return {
        "candidates_total": int(total_candidates),
        "conflict_pair_count": int(len(conflicts)),
        "inter_block_conflict_count": int(inter_block),
        "intra_block_exclusion_pairs": int(intra_excl),
        "conflict_density": float((len(conflicts) / max_pairs) if max_pairs else 0.0),
        "inter_block_conflict_density": float((inter_block / max_pairs) if max_pairs else 0.0),
    }


def snapshot(*, stride_xy: int, cap: int = 48) -> Dict[str, Any]:
    w = ObjectiveWeights(
        active_sectors=1.0,
        skyline_height=1.0,
        compactness=1.0,
        density_deviation=1.0,
        compatibility=1.0,
        accessibility=0.5,
    )
    scenario = generate_scenario(
        seed=123,
        preset="small",
        density_target=0.55,
        compatibility_strength=1.0,
        objective_weights=w,
    )
    cfg = SolverRunConfig(
        seed=123,
        strict_parity_mode=True,
        sector_balanced_candidates=True,
        max_candidates_per_block_override=int(cap),
        stride_xy_override=int(stride_xy),
        max_time_seconds=4.0,
        max_iterations=35,
        penalty_scale=60.0,
        conflict_penalty_multiplier=6.0,
    )
    gp = candidate_grid_params(scenario, cfg)
    cand_map = generate_candidates(
        scenario,
        stride_xy=gp["stride_xy"],
        stride_z=gp["stride_z"],
        max_candidates_per_block=gp["max_candidates_per_block"],
        strict_parity_mode=cfg.strict_parity_mode,
        sector_balanced=cfg.sector_balanced_candidates,
    )
    sector_union = sorted({p.sector_id for arr in cand_map.values() for p in arr})
    per_sector = _counts_per_sector(cand_map)
    per_block = _block_summaries(scenario, cand_map, cap=int(gp["max_candidates_per_block"]))
    conflict = _conflict_summary(cand_map)

    ach = density_achievability_report(scenario, cfg)
    attach_benchmark_hygiene_metadata(ach, density_target_requested=0.55, density_clamp_applied=False)

    return {
        "stride_xy": int(stride_xy),
        "cap": int(cap),
        "grid": dict(gp),
        "sector_union": sector_union,
        "candidates_per_sector": per_sector,
        "candidates_per_block": per_block,
        "conflicts": conflict,
        "density_achievability": {
            "achievable_density_min": float(ach.get("achievable_density_min", 0.0)),
            "achievable_density_max": float(ach.get("achievable_density_max", 0.0)),
            "achievability_degenerate": bool(ach.get("achievability_degenerate", False)),
            "target_inside_achievable_band": bool(ach.get("target_inside_achievable_band", False)),
            "benchmark_comparable": bool(ach.get("benchmark_comparable", False)),
        },
    }


def main() -> None:
    out_dir = Path(__file__).resolve().parents[3] / "evidence" / "small_stride_xy_counterfactual_seed123"
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline = snapshot(stride_xy=3, cap=48)
    finer = snapshot(stride_xy=2, cap=48)
    payload = {
        "preset": "small",
        "seed": 123,
        "sector_balanced_candidates": True,
        "strict_parity_mode": True,
        "cap": 48,
        "stride_z": 2,
        "baseline": baseline,
        "finer_grid": finer,
        "gate_benchmark_comparable": bool(finer["density_achievability"]["benchmark_comparable"]),
    }
    out_path = out_dir / "report.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

