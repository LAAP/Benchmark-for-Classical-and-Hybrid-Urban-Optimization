from __future__ import annotations

"""
Density achievability diagnostics and benchmark comparability flags.

These helpers are used to separate:
- structural target incompatibility (candidate-space issue),
- solver failure (search/optimization issue).
"""

from typing import Dict, List

from app.domain.formulation import generate_candidates
from app.domain.models import Scenario, SolverRunConfig

# Normalized achievable band narrower than this is treated as degenerate (point band).
ACHIEVABILITY_DEGENERATE_EPS = 1e-9


def density_achievability_report(scenario: Scenario, run_cfg: SolverRunConfig) -> Dict[str, object]:
    strict = run_cfg.strict_parity_mode
    small = len(scenario.blocks) <= 4
    if run_cfg.stride_xy_override is not None:
        try:
            stride_xy = max(1, int(run_cfg.stride_xy_override))
        except Exception:
            stride_xy = 1
    else:
        stride_xy = 3 if strict else (3 if small else 2)
    stride_z = 2
    override = run_cfg.max_candidates_per_block_override
    if override is not None:
        try:
            cap = max(1, int(override))
        except Exception:
            cap = 1
    else:
        cap = 20 if small else (24 if strict else 80)
    cands = generate_candidates(
        scenario,
        stride_xy=stride_xy,
        stride_z=stride_z,
        max_candidates_per_block=cap,
        strict_parity_mode=strict,
        sector_balanced=run_cfg.sector_balanced_candidates,
    )

    # Structural envelope from raw block ranges (independent of candidate truncation).
    min_total = sum(b.density_weight * b.min_height for b in scenario.blocks)
    max_total = sum(b.density_weight * b.max_height for b in scenario.blocks)
    span = max(1e-9, max_total - min_total)

    # Candidate-derived envelope under active grid/cap settings.
    # This is the quantity used for benchmark-comparable vs diagnostic interpretation.
    item_ranges: List[Dict[str, object]] = []
    min_total_sum = 0.0
    max_total_sum = 0.0
    for b in scenario.blocks:
        totals = []
        for c in cands[b.id]:
            totals.append(b.density_weight * c.height)
        tmin = min(totals) if totals else (b.density_weight * b.min_height)
        tmax = max(totals) if totals else (b.density_weight * b.max_height)
        min_total_sum += tmin
        max_total_sum += tmax
        item_ranges.append(
            {
                "block_id": b.id,
                "candidate_count": len(cands[b.id]),
                "density_total_min": float(tmin),
                "density_total_max": float(tmax),
            }
        )

    # Normalize candidate-achievable total density to same [0,1] scale as evaluation.
    ach_min = (min_total_sum - min_total) / span
    ach_max = (max_total_sum - min_total) / span
    # Clamp tiny numeric drift.
    ach_min = max(0.0, min(1.0, ach_min))
    ach_max = max(0.0, min(1.0, ach_max))
    valid = ach_min <= ach_max and 0.0 <= ach_min <= 1.0 and 0.0 <= ach_max <= 1.0

    target = float(scenario.density_target)
    inside = valid and (ach_min <= target <= ach_max)
    if not valid:
        margin = 0.0
    elif inside:
        margin = min(target - ach_min, ach_max - target)
    elif target < ach_min:
        margin = target - ach_min
    else:
        margin = ach_max - target

    truncation_risk = any(i["candidate_count"] >= cap for i in item_ranges)
    return {
        "achievable_density_min": float(ach_min),
        "achievable_density_max": float(ach_max),
        "target_density": target,
        "achievability_valid": bool(valid),
        "target_inside_achievable_band": bool(inside),
        "feasibility_margin": float(margin),
        "candidate_truncation_risk": bool(truncation_risk),
        "candidate_cap_used": cap,
        "global_density_total_min": float(min_total),
        "global_density_total_max": float(max_total),
        "strict_parity_mode": strict,
        "items": item_ranges,
    }


def attach_benchmark_hygiene_metadata(
    report: Dict[str, object],
    *,
    density_target_requested: float,
    density_clamp_applied: bool = False,
    density_target_adjusted_value: float | None = None,
) -> Dict[str, object]:
    """
    Augment achievability report with benchmark-interpretation flags (does not mutate Scenario).

    adjustment_allowed: only non-degenerate valid bands may be silently clamped in explicit-fallback mode.
    benchmark_comparable: valid band, non-degenerate, requested target lies inside band.
    """
    valid = bool(report.get("achievability_valid", False))
    ach_min = float(report.get("achievable_density_min", 0.0))
    ach_max = float(report.get("achievable_density_max", 0.0))
    width = ach_max - ach_min
    degenerate = (not valid) or (width <= ACHIEVABILITY_DEGENERATE_EPS)
    inside = bool(report.get("target_inside_achievable_band", False))

    adjustment_allowed = valid and not degenerate and (ach_max > ach_min + ACHIEVABILITY_DEGENERATE_EPS)
    benchmark_comparable = valid and not degenerate and inside
    out_of_band = valid and not degenerate and not inside
    structurally_infeasible = degenerate or (valid and not inside)

    report["achievability_band_width"] = float(width)
    report["achievability_degenerate"] = bool(degenerate)
    report["adjustment_allowed"] = bool(adjustment_allowed)
    report["benchmark_comparable"] = bool(benchmark_comparable)
    report["benchmark_out_of_band"] = bool(out_of_band)
    report["benchmark_structurally_infeasible_target"] = bool(structurally_infeasible)
    report["benchmark_non_comparable"] = not benchmark_comparable
    report["density_target_requested"] = float(density_target_requested)
    report["density_target_stored_for_solve"] = float(report.get("target_density", density_target_requested))
    report["density_clamp_applied"] = bool(density_clamp_applied)
    report["density_target_adjusted_value"] = density_target_adjusted_value
    return report
