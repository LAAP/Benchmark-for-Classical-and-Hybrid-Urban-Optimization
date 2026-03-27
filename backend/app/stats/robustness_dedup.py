from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List, Tuple

from app.domain.robustness_fingerprint import (
    fingerprint_definition_text,
    sweep_instance_layout_fingerprint,
)


def _table_row_from_instance(inst: Dict[str, Any]) -> Dict[str, Any]:
    """Align with robustness_table fields when present on instance."""
    seed = inst["scenario_seed"]
    f = inst["features"]
    c = inst["classical"]
    h = inst["hybrid"]
    ov_c = c.get("overlap_violations")
    if ov_c is None:
        ov_c = c.get("violation_breakdown", {}).get("overlap_violations", 0)
    ov_h = h.get("overlap_violations")
    if ov_h is None:
        ov_h = h.get("violation_breakdown", {}).get("overlap_violations", 0)
    dv_c = c.get("density_violations")
    if dv_c is None:
        dv_c = c.get("violation_breakdown", {}).get("density_violations", 0)
    dv_h = h.get("density_violations")
    if dv_h is None:
        dv_h = h.get("violation_breakdown", {}).get("density_violations", 0)
    return {
        "seed": seed,
        "scenario_id": inst["scenario_id"],
        "cand_total": f["candidates_total"],
        "conflict_pair_count": f["conflict_pair_count"],
        "conflict_density": round(float(f["conflict_density"]), 5),
        "inter_block_conflicts": f["inter_block_conflict_count"],
        "inter_block_conflict_density": round(float(f["inter_block_conflict_density"]), 5),
        "occupancy_pressure": round(float(f["occupancy_pressure_volume"]), 4),
        "footprint_pressure": round(float(f["max_block_footprint_ratio_vs_smallest_sector"]), 4),
        "truncation_risk": f["candidate_truncation_risk"],
        "classical_feasible": c["feasible"],
        "hybrid_feasible": h["feasible"],
        "overlap_violations_classical": int(ov_c),
        "overlap_violations_hybrid": int(ov_h),
        "density_violations_classical": int(dv_c),
        "density_violations_hybrid": int(dv_h),
        "runtime_classical_ms": round(float(c.get("runtime_ms", 0)), 2),
        "runtime_hybrid_ms": round(float(h.get("runtime_ms", 0)), 2),
        "difficulty": inst["difficulty"],
    }


def deduplicate_robustness_sweep(sweep: Dict[str, Any]) -> Dict[str, Any]:
    """
    Group sweep `instances` by layout fingerprint; one logical geometry per group.
    Outcomes are identical for identical scenario inputs; representative row = min(seed) instance.
    """
    instances: List[Dict[str, Any]] = list(sweep.get("instances") or [])
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for inst in instances:
        fp = sweep_instance_layout_fingerprint(inst)
        groups.setdefault(fp, []).append(inst)

    raw_n = len(instances)
    unique_n = len(groups)
    duplication_factor = (raw_n / unique_n) if unique_n else 0.0

    group_summaries = []
    dedup_table = []

    for fp, members in sorted(groups.items(), key=lambda kv: min(m["scenario_seed"] for m in kv[1])):
        members_sorted = sorted(members, key=lambda m: m["scenario_seed"])
        rep = members_sorted[0]
        seeds = [m["scenario_seed"] for m in members_sorted]
        row = _table_row_from_instance(rep)
        row["layout_fingerprint"] = fp
        row["group_size"] = len(members)
        row["seeds_in_group"] = seeds
        row["representative_seed"] = rep["scenario_seed"]
        dedup_table.append(row)
        group_summaries.append(
            {
                "layout_fingerprint": fp,
                "group_size": len(members),
                "seeds": seeds,
                "representative_seed": rep["scenario_seed"],
            }
        )

    # Counts by difficulty on dedup set
    diff_counts = {"easy": 0, "moderate": 0, "hard": 0}
    for r in dedup_table:
        diff_counts[r["difficulty"]] = diff_counts.get(r["difficulty"], 0) + 1

    raw_diff = {"easy": 0, "moderate": 0, "hard": 0}
    for inst in instances:
        raw_diff[inst["difficulty"]] = raw_diff.get(inst["difficulty"], 0) + 1

    return {
        "version": "v1.6.2",
        "fingerprint_definition": fingerprint_definition_text(),
        "raw_instance_count": raw_n,
        "unique_layout_count": unique_n,
        "duplication_factor_raw_per_unique": round(duplication_factor, 4),
        "duplicate_groups": [g for g in group_summaries if g["group_size"] > 1],
        "group_summaries": group_summaries,
        "difficulty_counts_raw": raw_diff,
        "difficulty_counts_dedup": diff_counts,
        "dedup_feature_means_by_difficulty": three_way_feature_means_dedup(dedup_table),
        "dedup_table": dedup_table,
        "source_study_label": sweep.get("study_label"),
        "source_fairness_classification": sweep.get("fairness_classification"),
    }


def three_way_feature_means_dedup(dedup_table: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Descriptive means by difficulty on unique layouts only."""
    numeric_keys = [
        "conflict_pair_count",
        "conflict_density",
        "inter_block_conflicts",
        "inter_block_conflict_density",
        "occupancy_pressure",
        "footprint_pressure",
        "cand_total",
    ]
    groups: Dict[str, List[Dict[str, Any]]] = {"easy": [], "moderate": [], "hard": []}
    for r in dedup_table:
        groups.setdefault(r["difficulty"], []).append(r)
    out: Dict[str, Dict[str, Any]] = {}
    for key in numeric_keys:
        out[key] = {}
        for gname in ("easy", "moderate", "hard"):
            vals = [float(row[key]) for row in groups.get(gname, []) if key in row]
            out[key][gname] = round(mean(vals), 6) if vals else None
    return out
