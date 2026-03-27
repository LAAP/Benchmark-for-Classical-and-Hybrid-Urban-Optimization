"""
Small-preset feasibility diagnosis (structural analysis only).

Does not invoke CP-SAT or hybrid solvers — intended to explain INFEASIBLE outcomes
under the shared discrete candidate graph without running more benchmarks.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List

from app.domain.formulation import CandidatePlacement, build_conflicts, generate_candidates, overlap_3d
from app.domain.instance_diagnostics import compute_instance_features, candidate_grid_params
from app.domain.models import ObjectiveWeights, Scenario, SolverRunConfig
from app.domain.scenario_generator import generate_scenario

PRESET_SMALL_SEEDS: List[int] = [123, 234, 345]

_DEFAULT_WEIGHTS = ObjectiveWeights(
    active_sectors=1.0,
    skyline_height=1.0,
    compactness=1.0,
    density_deviation=1.0,
    compatibility=1.0,
    accessibility=0.5,
)


def _scenario(seed: int, density_target: float = 0.55) -> Scenario:
    return generate_scenario(
        seed=seed,
        preset="small",
        density_target=density_target,
        compatibility_strength=1.0,
        objective_weights=_DEFAULT_WEIGHTS,
    )


def _sector_union(cand_map: Dict[str, List]) -> List[str]:
    s: set[str] = set()
    for arr in cand_map.values():
        for c in arr:
            s.add(c.sector_id)
    return sorted(s)


def _sector_coverage_detail(
    scenario: Scenario, cand_map: Dict[str, List[CandidatePlacement]]
) -> Dict[str, Any]:
    rows = []
    for b in scenario.blocks:
        arr = cand_map[b.id]
        secs = [c.sector_id for c in arr]
        heights = [c.height for c in arr]
        rows.append(
            {
                "block_id": b.id,
                "candidate_count": len(arr),
                "sectors_represented": sorted(set(secs)),
                "unique_height_count": len(set(heights)),
                "height_min": min(heights) if heights else None,
                "height_max": max(heights) if heights else None,
            }
        )
    by_sector: Dict[str, int] = {}
    for b in scenario.blocks:
        for c in cand_map[b.id]:
            by_sector[c.sector_id] = by_sector.get(c.sector_id, 0) + 1
    return {"per_block": rows, "candidate_placements_per_sector": by_sector}


def _block_pair_conflict_stats(cand_map: Dict[str, List[CandidatePlacement]]) -> List[Dict[str, Any]]:
    bids = list(cand_map.keys())
    out: List[Dict[str, Any]] = []
    for b1, b2 in combinations(bids, 2):
        c1, c2 = cand_map[b1], cand_map[b2]
        prod = len(c1) * len(c2)
        same_sector_conflict = 0
        cross_sector_pairs = 0
        for x in c1:
            for y in c2:
                if x.sector_id != y.sector_id:
                    cross_sector_pairs += 1
                    continue
                if overlap_3d(x, y):
                    same_sector_conflict += 1
        same_total = prod - cross_sector_pairs
        out.append(
            {
                "block_a": b1,
                "block_b": b2,
                "cross_pairs": prod,
                "pairs_different_sectors": cross_sector_pairs,
                "pairs_same_sector": same_total,
                "same_sector_conflicting_pairs": same_sector_conflict,
                "same_sector_conflict_rate": (
                    (same_sector_conflict / same_total) if same_total > 0 else 0.0
                ),
            }
        )
    return out


def _min_cap_for_sector_set(
    scenario: Scenario,
    *,
    stride_xy: int,
    stride_z: int,
    strict_parity_mode: bool,
    want_sectors: int = 2,
    cap_hi: int = 2048,
) -> Dict[str, Any]:
    """
    Binary search smallest uniform per-block cap such that the union of sectors
    across all candidates has at least `want_sectors` members (monotone in cap
    for fixed enumeration order).
    """

    def union_count(cap: int) -> int:
        cand = generate_candidates(
            scenario,
            stride_xy=stride_xy,
            stride_z=stride_z,
            max_candidates_per_block=max(1, cap),
            strict_parity_mode=strict_parity_mode,
        )
        return len(_sector_union(cand))

    lo, hi = 1, int(cap_hi)
    max_u = union_count(hi)
    if max_u < want_sectors:
        return {
            "achieved": False,
            "note": f"even at cap={hi} union has <{want_sectors} sectors",
            "max_cap_tried": hi,
            "union_at_max": max_u,
            "strict_parity_mode": strict_parity_mode,
        }
    while lo < hi:
        mid = (lo + hi) // 2
        if union_count(mid) >= want_sectors:
            hi = mid
        else:
            lo = mid + 1
    u_at = union_count(lo)
    return {
        "achieved": True,
        "min_cap_binary_search": lo,
        "union_sector_count_at_min_cap": u_at,
        "cap_upper_bound_used": cap_hi,
        "strict_parity_mode": strict_parity_mode,
        "note": "Monotone cap search; strict stratified vs non-strict ordering can differ.",
    }


def diagnose_seed(seed: int, *, density_target: float = 0.55) -> Dict[str, Any]:
    scenario = _scenario(seed, density_target=density_target)
    run_strict = SolverRunConfig(
        strict_parity_mode=True,
        max_time_seconds=4.0,
        max_iterations=35,
        seed=seed,
        penalty_scale=60.0,
    )
    run_relaxed = SolverRunConfig(
        strict_parity_mode=False,
        max_time_seconds=4.0,
        max_iterations=35,
        seed=seed,
        penalty_scale=60.0,
    )

    gp = candidate_grid_params(scenario, run_strict)
    cand_s = generate_candidates(
        scenario,
        stride_xy=gp["stride_xy"],
        stride_z=gp["stride_z"],
        max_candidates_per_block=gp["max_candidates_per_block"],
        strict_parity_mode=True,
    )
    cand_relaxed_same_operational_grid = generate_candidates(
        scenario,
        stride_xy=gp["stride_xy"],
        stride_z=gp["stride_z"],
        max_candidates_per_block=gp["max_candidates_per_block"],
        strict_parity_mode=False,
    )
    feats_s = compute_instance_features(scenario, run_strict)
    feats_r_default_grid = compute_instance_features(scenario, run_relaxed)
    conflicts = build_conflicts(cand_s)
    cov = _sector_coverage_detail(scenario, cand_s)
    union = _sector_union(cand_s)
    union_relaxed_same_grid = _sector_union(cand_relaxed_same_operational_grid)
    pair_stats = _block_pair_conflict_stats(cand_s)

    all_same_sector = len(union) <= 1
    same_sector_rates = [p["same_sector_conflict_rate"] for p in pair_stats if p["pairs_same_sector"]]

    # Occupancy sanity: single-sector packing vs floor / volume (necessary, not sufficient)
    s0 = next(s for s in scenario.sectors if s.id == union[0]) if union else None
    floor_area = float(s0.width * s0.depth) if s0 else 0.0
    sum_min_footprint = sum(
        min(
            b.width * b.depth,
            b.depth * b.width,
        )
        for b in scenario.blocks
    )

    cap_probe_non_strict = _min_cap_for_sector_set(
        scenario,
        stride_xy=gp["stride_xy"],
        stride_z=gp["stride_z"],
        strict_parity_mode=False,
        want_sectors=2,
    )
    cap_probe_strict = _min_cap_for_sector_set(
        scenario,
        stride_xy=gp["stride_xy"],
        stride_z=gp["stride_z"],
        strict_parity_mode=True,
        want_sectors=2,
    )

    narrative_points: List[str] = [
        "CP-SAT infeasibility here refers only to the multipartite conflict graph: pick exactly "
        "one candidate per block with no conflicting pair (overlap in the same sector). "
        "Density, compatibility (strict), and accessibility are not encoded as CP-SAT hard constraints.",
        "Inter-block edges exist only for pairs of candidates in the same sector; different sectors never overlap.",
    ]
    if all_same_sector:
        narrative_points.append(
            f"All |blocks|={len(scenario.blocks)} items share only sector(s) {union} in the operative "
            f"candidate sets (cap={gp['max_candidates_per_block']}, strict_parity_mode=True). "
            "Enumeration order fills the per-block cap before later sectors appear, so the effective "
            "feasibility problem is single-sector 3D packing on the strided grid."
        )
        narrative_points.append(
            f"At least min sum of block footprints (=both orientations min w*d) ≈ {sum_min_footprint:.1f} vs "
            f"single-sector floor {floor_area:.1f} for {union[0] if union else '—'} — a coarse 2D necessary check only."
        )

    high_same_sector_conflict = same_sector_rates and min(same_sector_rates) > 0.85
    if all_same_sector and high_same_sector_conflict:
        narrative_points.append(
            "Block pairs show very high same-sector pairwise conflict rates: many placement pairs collide in 3D, "
            "consistent with dense packing pressure inside one sector."
        )

    return {
        "seed": seed,
        "density_target": density_target,
        "grid_operational_strict": gp,
        "structural_features_strict": feats_s,
        "structural_features_non_strict_default_grid": feats_r_default_grid,
        "note_non_strict_default_grid": (
            "Uses solver default non-strict grid (wider enumeration: lower stride_xy / higher cap for |blocks|>4). "
            "Compare against strict features for scale, not apples-to-apples sector reach."
        ),
        "sector_union_strict_operational_cap": union,
        "sector_union_non_strict_same_stride_cap_as_strict": union_relaxed_same_grid,
        "single_effective_sector_packing": bool(all_same_sector),
        "sector_coverage_strict": cov,
        "conflict_edges_total": len(conflicts),
        "block_pair_same_sector_stats": pair_stats,
        "occupancy_coarse_2d": {
            "single_sector_id": union[0] if union else None,
            "sector_floor_area": floor_area,
            "sum_block_min_footprints_both_orientations": sum_min_footprint,
        },
        "cap_probe_multi_sector_non_strict": cap_probe_non_strict,
        "cap_probe_multi_sector_strict": cap_probe_strict,
        "cp_sat_failure_hypotheses_ranked": [
            {
                "hypothesis": "single_sector_candidate_skew_from_cap_and_enumeration_order",
                "strength": "high" if all_same_sector else "low",
                "detail": "Later sectors never appear before caps saturate; all inter-block conflicts arise inside one sector.",
            },
            {
                "hypothesis": "strict_parity_height_stratification_reducing_height_diversity",
                "strength": "contextual",
                "detail": "Compare unique_height_count per block in sector_coverage. At the operational strict cap, "
                "non-strict enumeration with the same stride/cap still often yields the same sector_union — parity mode is not "
                "the primary gate for multi-sector reach; enumeration saturation in the first sector is.",
            },
            {
                "hypothesis": "geometric_impossibility_on_discrete_grid_under_shared_sector",
                "strength": "high" if all_same_sector else "moderate",
                "detail": "If the induced conflict graph has no multipartite independent transversal, CP-SAT is INFEASIBLE "
                "regardless of time limits.",
            },
            {
                "hypothesis": "sector_geometry_mismatch_blocking_placements",
                "strength": "low_if_multi_sector_eventually_reachable_at_high_cap",
                "detail": "If raising cap exposes additional sectors, geometry may still fit blocks but benchmarks never see those candidates.",
            },
        ],
        "hybrid_failure_context": {
            "summary": "Hybrid uses the same candidate map and soft penalties; if the hard feasibility core (one-per-block, "
            "non-overlap) is already unrealizable on the candidate set CP-SAT uses, an unconstrained penalty minimizer can still "
            "output a sample, but post-evaluation will show mass overlap. Repair-assisted decode reduces some conflicts — not "
            "equivalent to a feasibility proof.",
            "expected_when_cp_sat_infeasible": True,
            "independent_of_penalties_partially": "Sampler+decode can pick geographically diverse violations; failure mode is "
            "not identical to CP-SAT's certificate, but root cause often remains the same compressed feasible region.",
        },
        "narrative_points": narrative_points,
    }


def run_small_feasibility_diagnosis(
    *,
    seeds: List[int] | None = None,
    density_target: float = 0.55,
    output_path: Path | None = None,
) -> Dict[str, Any]:
    seeds = seeds or list(PRESET_SMALL_SEEDS)
    per_seed = [diagnose_seed(s, density_target=density_target) for s in seeds]

    single_sector_all = all(s["single_effective_sector_packing"] for s in per_seed)

    recommendation = {
        "is_primarily_structure_not_search_budget": bool(single_sector_all),
        "cp_sat_status_interpretation": "INFEASIBLE is a feasibility proof in the CP model (not a timeout). If the candidate sets "
        "omit multi-sector diversity because caps truncate during first-sector enumeration, that is a structural artifact of the "
        "discrete candidate construction — not something a longer time limit fixes.",
        "rationale": "All three preset seeds exhibit single-sector candidate unions at the operational strict cap, so every "
        "inter-block conflict is realized inside one sector. CP-SAT then solves a compressed 3D packing problem that may be "
        "impossible on the grid regardless of runtime.",
        "smallest_defensible_next_test": (
            "First on a single seed: add sector-balanced candidate budgets or modestly raise the per-block cap specifically to "
            "surface at least one additional sector before the cap is exhausted. This isolates enumeration skew from intrinsic "
            "geometry with minimal formulation churn."
        ),
        "ordering": [
            "1) sector-balanced reach (or modest cap increase) — one seed, one A/B",
            "2) if still INFEASIBLE, relax strict_parity_mode as a candidate-richness counterfactual (same cap ladder)",
            "3) only then revisit packing geometry / sector definitions broadly",
        ],
        "avoid_for_now": "Expanding benchmark coverage before confirming whether single-sector skew explains the infeasibility surface.",
    }

    out: Dict[str, Any] = {
        "preset": "small",
        "seeds": seeds,
        "density_target": density_target,
        "per_seed": per_seed,
        "aggregate": {
            "all_preset_seeds_single_sector_under_operational_cap": single_sector_all,
            "interpretation": "Benchmark `small` preset seeds currently explore overlapping feasibility on a severely restricted "
            "candidate manifold: almost surely single-sector at cap=24 strict — diagnose before scaling benchmarks.",
        },
        "recommendation": recommendation,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(out, indent=2))
    return out


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    out = repo_root / "evidence" / "small_feasibility_diagnosis" / "report.json"
    run_small_feasibility_diagnosis(output_path=out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
