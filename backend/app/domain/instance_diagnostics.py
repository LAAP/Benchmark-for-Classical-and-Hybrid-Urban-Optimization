from __future__ import annotations

from statistics import mean, pstdev
from typing import Any, Dict, List

from typing import Literal

from app.domain.density_diagnostics import attach_benchmark_hygiene_metadata, density_achievability_report
from app.domain.formulation import build_conflicts, generate_candidates
from app.domain.models import Scenario, SolverRunConfig


def candidate_grid_params(scenario: Scenario, config: SolverRunConfig) -> Dict[str, int]:
    """Matches solvers/QUBO builder grid (toy: 6 blocks -> not small)."""
    small = len(scenario.blocks) <= 4
    strict = config.strict_parity_mode
    override = config.max_candidates_per_block_override
    stride_override = config.stride_xy_override
    if override is not None:
        try:
            override_i = int(override)
        except Exception:
            override_i = 0
        override_i = max(1, override_i)
    else:
        override_i = 0
    if stride_override is not None:
        try:
            stride_xy = max(1, int(stride_override))
        except Exception:
            stride_xy = 1
    else:
        stride_xy = 3 if strict else (3 if small else 2)
    return {
        "stride_xy": stride_xy,
        "stride_z": 2,
        "max_candidates_per_block": override_i if override is not None else (20 if small else (24 if strict else 80)),
    }


def apply_density_target_adjustment_if_valid(
    scenario: Scenario,
    run_cfg: SolverRunConfig,
    *,
    density_clamp_mode: Literal["off", "explicit_fallback"] = "off",
) -> Dict[str, Any]:
    """
    Optional density clamp only in explicit_fallback mode and only when adjustment_allowed
    (non-degenerate band). Default off: scenario.density_target unchanged; metadata explains achievability.
    """
    requested = float(scenario.density_target)
    density_report = density_achievability_report(scenario, run_cfg)
    attach_benchmark_hygiene_metadata(
        density_report,
        density_target_requested=requested,
        density_clamp_applied=False,
        density_target_adjusted_value=None,
    )
    density_report["target_adjustment_applied"] = False
    density_report["target_adjusted_for_feasibility"] = float(scenario.density_target)

    if density_clamp_mode == "explicit_fallback" and density_report.get("adjustment_allowed") and not density_report.get(
        "target_inside_achievable_band", True
    ):
        lo = float(density_report["achievable_density_min"])
        hi = float(density_report["achievable_density_max"])
        if lo <= hi:
            scenario.density_target = min(max(float(scenario.density_target), lo), hi)
            density_report = density_achievability_report(scenario, run_cfg)
            density_report["target_adjustment_applied"] = True
            density_report["target_adjusted_for_feasibility"] = float(scenario.density_target)
            density_report["density_clamp_mode"] = "explicit_fallback"
            attach_benchmark_hygiene_metadata(
                density_report,
                density_target_requested=requested,
                density_clamp_applied=True,
                density_target_adjusted_value=float(scenario.density_target),
            )
    elif not density_report.get("achievability_valid", False):
        density_report["target_adjustment_reason"] = "achievability_invalid_no_adjustment"
    return density_report


def compute_instance_features(scenario: Scenario, run_cfg: SolverRunConfig) -> Dict[str, Any]:
    """
    Structural features for toy robustness (v1.6). Grid matches CP-SAT / hybrid (`candidate_grid_params`).

    **Feature definitions (all on the shared candidate graph):**

    - **candidates_per_block / candidates_total**: discrete placement counts after cap/truncation.
    - **conflict_pair_count**: |`build_conflicts`| — undirected pairs that cannot be selected together
      (intra-block exclusivity + inter-block 3D overlaps on the grid).
    - **inter_block_conflict_count**: conflict pairs whose endpoints belong to different blocks (geometric
      packing pressure within a sector).
    - **conflict_density**: conflict_pair_count / C(N,2) over all candidates N (global graph density).
    - **inter_block_conflict_density**: inter_block_conflict_count / C(N,2).
    - **occupancy_pressure_volume**: sum(block floor × min_height) / sum(sector volume) — lower bound volume
      if every block uses minimum height vs aggregate sector capacity (structural, not a solver assignment).
    - **max_block_footprint_ratio_vs_smallest_sector**: max over blocks of (w×d) / smallest sector floor area.
    - **blocks_per_sector**: |blocks| / |sectors|.
    - **candidate_truncation_risk**: any block hit `max_candidates_per_block` cap.
    - **candidate_count_cv**: dispersion of per-block candidate counts (imbalance / degeneracy proxy).
    - **mean_block_height_span_levels**: mean((max_h − min_h + 1)) — vertical solution freedom per item.
    """
    gp = candidate_grid_params(scenario, run_cfg)
    cand_map = generate_candidates(
        scenario,
        stride_xy=gp["stride_xy"],
        stride_z=gp["stride_z"],
        max_candidates_per_block=gp["max_candidates_per_block"],
        strict_parity_mode=run_cfg.strict_parity_mode,
        sector_balanced=run_cfg.sector_balanced_candidates,
    )
    cap = gp["max_candidates_per_block"]
    per_block = [len(cand_map[b.id]) for b in scenario.blocks]
    total_candidates = sum(per_block)
    max_pairs = max(0, total_candidates * (total_candidates - 1) // 2)

    conflicts = build_conflicts(cand_map)
    pid_to_block: Dict[str, str] = {}
    for bid, arr in cand_map.items():
        for c in arr:
            pid_to_block[c.placement_id] = bid
    intra_block_exclusion_pairs = sum(len(cand_map[bid]) * (len(cand_map[bid]) - 1) // 2 for bid in cand_map)
    inter_block_conflicts = sum(
        1 for pa, pb in conflicts if pid_to_block.get(pa) != pid_to_block.get(pb)
    )

    conflict_pair_count = len(conflicts)
    conflict_density = (conflict_pair_count / max_pairs) if max_pairs > 0 else 0.0
    inter_density = (inter_block_conflicts / max_pairs) if max_pairs > 0 else 0.0

    sector_floor = {s.id: float(s.width * s.depth) for s in scenario.sectors}
    min_sector_floor = min(sector_floor.values()) if sector_floor else 1.0
    max_block_footprint_ratio = max((b.width * b.depth) / min_sector_floor for b in scenario.blocks) if scenario.blocks else 0.0

    sum_sector_vol = sum(float(s.width * s.depth * s.max_height) for s in scenario.sectors)
    min_block_vol = sum(float(b.width * b.depth * b.min_height) for b in scenario.blocks)
    occupancy_pressure = (min_block_vol / sum_sector_vol) if sum_sector_vol > 0 else 0.0

    blocks_per_sector = len(scenario.blocks) / max(1, len(scenario.sectors))

    truncation_risk = any(n >= cap for n in per_block)
    cand_count_cv = (pstdev(per_block) / mean(per_block)) if len(per_block) > 1 and mean(per_block) > 0 else 0.0

    height_ranges = [b.max_height - b.min_height + 1 for b in scenario.blocks]
    mean_height_span = float(mean(height_ranges)) if height_ranges else 0.0

    return {
        "grid": gp,
        "candidates_per_block": {b.id: len(cand_map[b.id]) for b in scenario.blocks},
        "candidates_total": total_candidates,
        "candidates_mean_per_block": float(mean(per_block)) if per_block else 0.0,
        "candidates_min_per_block": min(per_block) if per_block else 0,
        "candidates_max_per_block": max(per_block) if per_block else 0,
        "candidate_count_cv": float(cand_count_cv),
        "conflict_pair_count": conflict_pair_count,
        "inter_block_conflict_count": inter_block_conflicts,
        "intra_block_exclusion_pairs": intra_block_exclusion_pairs,
        "conflict_density": float(conflict_density),
        "inter_block_conflict_density": float(inter_density),
        "occupancy_pressure_volume": float(occupancy_pressure),
        "max_block_footprint_ratio_vs_smallest_sector": float(max_block_footprint_ratio),
        "blocks_per_sector": float(blocks_per_sector),
        "candidate_truncation_risk": bool(truncation_risk),
        "mean_block_height_span_levels": float(mean_height_span),
        "symmetry_note": "candidate_count_cv captures imbalance across items; degenerate duplicate placements not enumerated",
    }


def classify_instance_difficulty(classical_feasible: bool, hybrid_feasible: bool) -> str:
    if classical_feasible and hybrid_feasible:
        return "easy"
    if not classical_feasible and not hybrid_feasible:
        return "hard"
    return "moderate"


def feature_contrast_summary(rows: List[Dict[str, Any]], numeric_keys: List[str]) -> List[Dict[str, Any]]:
    """Descriptive easy vs hard means; small-N, not inferential."""
    easy = [r for r in rows if r.get("difficulty") == "easy"]
    hard = [r for r in rows if r.get("difficulty") == "hard"]
    out: List[Dict[str, Any]] = []
    for key in numeric_keys:
        fe = [float(r["features"][key]) for r in easy if key in r.get("features", {})]
        fh = [float(r["features"][key]) for r in hard if key in r.get("features", {})]
        if not fe or not fh:
            out.append({"feature": key, "mean_easy": None, "mean_hard": None, "delta_hard_minus_easy": None})
            continue
        me, mh = mean(fe), mean(fh)
        out.append(
            {
                "feature": key,
                "mean_easy": me,
                "mean_hard": mh,
                "delta_hard_minus_easy": mh - me,
            }
        )
    out.sort(key=lambda x: abs(x["delta_hard_minus_easy"] or 0.0), reverse=True)
    return out
