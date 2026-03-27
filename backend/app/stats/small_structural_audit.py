from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.domain.density_diagnostics import attach_benchmark_hygiene_metadata, density_achievability_report
from app.domain.formulation import generate_candidates
from app.domain.instance_diagnostics import candidate_grid_params, compute_instance_features
from app.domain.models import SolverRunConfig
from app.domain.scenario_generator import generate_scenario


@dataclass(frozen=True)
class CandidateHeightAudit:
    block_id: str
    candidate_count: int
    unique_height_count: int
    min_candidate_height: int | None
    max_candidate_height: int | None
    block_min_height: int
    block_max_height: int
    cap_hit: bool
    cap: int


def _candidate_height_audit_for_block(block, candidates: list) -> CandidateHeightAudit:
    heights = [int(c.height) for c in candidates]
    uniq = sorted(set(heights))
    return CandidateHeightAudit(
        block_id=str(block.id),
        candidate_count=len(candidates),
        unique_height_count=len(uniq),
        min_candidate_height=min(uniq) if uniq else None,
        max_candidate_height=max(uniq) if uniq else None,
        block_min_height=int(block.min_height),
        block_max_height=int(block.max_height),
        cap_hit=False,
        cap=0,
    )


def audit_seed(preset: str, seed: int, *, density_target: float = 0.55, strict_parity_mode: bool = True) -> Dict[str, Any]:
    scenario = generate_scenario(seed=seed, preset=preset, density_target=density_target)
    run_cfg = SolverRunConfig(strict_parity_mode=strict_parity_mode, seed=seed)
    grid = candidate_grid_params(scenario, run_cfg)
    cand_map = generate_candidates(
        scenario,
        stride_xy=grid["stride_xy"],
        stride_z=grid["stride_z"],
        max_candidates_per_block=grid["max_candidates_per_block"],
        strict_parity_mode=run_cfg.strict_parity_mode,
        sector_balanced=run_cfg.sector_balanced_candidates,
    )

    # Per-block audit: is height diversity present before truncation?
    cap = int(grid["max_candidates_per_block"])
    height_audits: List[Dict[str, Any]] = []
    for b in scenario.blocks:
        a = _candidate_height_audit_for_block(b, cand_map[b.id])
        # cap is per-block; generate_candidates stops at cap.
        a = CandidateHeightAudit(
            **{**asdict(a), "cap_hit": (len(cand_map[b.id]) >= cap), "cap": cap}
        )
        height_audits.append(asdict(a))

    rep = density_achievability_report(scenario, run_cfg)
    attach_benchmark_hygiene_metadata(rep, density_target_requested=float(density_target), density_clamp_applied=False)

    feats = compute_instance_features(scenario, run_cfg)

    # Diagnose collapse cause: if each block sees only one height in candidates, ach band collapses to a point.
    all_single_height = all(int(a["unique_height_count"]) <= 1 for a in height_audits)
    cause = []
    if all_single_height:
        cause.append("candidate_construction_height_truncation")
    if rep.get("achievability_degenerate"):
        cause.append("achievability_degenerate_point_band")
    if rep.get("candidate_truncation_risk"):
        cause.append("candidate_cap_truncation_risk")

    return {
        "preset": preset,
        "seed": seed,
        "density_target_requested": float(density_target),
        "grid_params": grid,
        "scenario_summary": {
            "block_count": len(scenario.blocks),
            "sector_count": len(scenario.sectors),
            "sector_dims": [{"id": s.id, "w": s.width, "d": s.depth, "max_h": s.max_height} for s in scenario.sectors],
        },
        "candidate_height_audit": height_audits,
        "density_achievability": rep,
        "features": {
            "candidates_total": feats.get("candidates_total"),
            "conflict_pair_count": feats.get("conflict_pair_count"),
            "conflict_density": feats.get("conflict_density"),
            "inter_block_conflict_count": feats.get("inter_block_conflict_count"),
            "occupancy_pressure_volume": feats.get("occupancy_pressure_volume"),
            "max_block_footprint_ratio_vs_smallest_sector": feats.get("max_block_footprint_ratio_vs_smallest_sector"),
        },
        "degeneracy_diagnosis": {
            "all_blocks_single_candidate_height": bool(all_single_height),
            "suspected_causes": cause,
            "interpretation": (
                "Achievable density band collapses when candidate set contains effectively a single height per block; "
                "then candidate-derived min==max totals and normalized ach_min==ach_max."
            ),
        },
    }


def run_audit(
    *,
    small_seeds: Iterable[int] = (123, 234, 345),
    toy_seeds: Iterable[int] = (111, 222, 333),
    density_target: float = 0.55,
    strict_parity_mode: bool = True,
) -> Dict[str, Any]:
    small_rows = [audit_seed("small", s, density_target=density_target, strict_parity_mode=strict_parity_mode) for s in small_seeds]
    toy_rows = [audit_seed("toy", s, density_target=density_target, strict_parity_mode=strict_parity_mode) for s in toy_seeds]

    def _compact(row: Dict[str, Any]) -> Dict[str, Any]:
        rep = row["density_achievability"]
        feats = row["features"]
        return {
            "preset": row["preset"],
            "seed": row["seed"],
            "cand_total": feats["candidates_total"],
            "conflict_density": feats["conflict_density"],
            "occupancy_pressure": feats["occupancy_pressure_volume"],
            "ach_min": rep["achievable_density_min"],
            "ach_max": rep["achievable_density_max"],
            "ach_degenerate": rep.get("achievability_degenerate"),
            "target": rep.get("density_target_requested"),
            "cap": row["grid_params"]["max_candidates_per_block"],
            "trunc_risk": rep.get("candidate_truncation_risk"),
            "all_single_height": row["degeneracy_diagnosis"]["all_blocks_single_candidate_height"],
        }

    comparison = [_compact(r) for r in toy_rows + small_rows]
    return {
        "study_label": "small structural formulation audit (no solver runs)",
        "density_target_requested": float(density_target),
        "strict_parity_mode": bool(strict_parity_mode),
        "toy": {"seeds": list(toy_seeds), "rows": toy_rows},
        "small": {"seeds": list(small_seeds), "rows": small_rows},
        "toy_vs_small_compact": comparison,
    }


def write_audit_artifacts(out: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    json_path.write_text(json.dumps(out, indent=2))

    csv_path = out_dir / "toy_vs_small_compact.csv"
    rows: List[Dict[str, Any]] = list(out.get("toy_vs_small_compact") or [])
    if rows:
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return {"report_json": str(json_path), "compact_csv": str(csv_path)}


if __name__ == "__main__":
    out = run_audit()
    root = Path(__file__).resolve().parents[3]
    artifacts = write_audit_artifacts(out, root / "evidence" / "small_structural_audit")
    print(json.dumps({"artifacts": artifacts}, indent=2))
