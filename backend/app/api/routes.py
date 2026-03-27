from __future__ import annotations

"""API orchestration layer: scenario generation, experiment execution, and reproducible exports."""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.storage import load_experiment, load_scenario, save_experiment, save_scenario
from app.core.benchmark_matrix import BENCHMARK_MATRIX
from app.domain.models import (
    ExperimentConfig,
    ExperimentRecord,
    ObjectiveWeights,
    Scenario,
    SolverKind,
    SolverRunConfig,
    TrialResult,
)
from app.domain.density_diagnostics import attach_benchmark_hygiene_metadata, density_achievability_report
from app.domain.instance_diagnostics import (
    apply_density_target_adjustment_if_valid,
    classify_instance_difficulty,
    compute_instance_features,
    feature_contrast_summary,
)
from app.domain.scenario_generator import generate_scenario
from app.solvers.classical_cpsat import CPSATSolver
from app.solvers.hybrid_solver import HybridQuboSolver
from app.stats.analysis import compute_experiment_stats, infer_experiment_fairness_classification
from app.stats.report_template import methodology_template_for_preset
from app.stats.robustness_dedup import deduplicate_robustness_sweep

router = APIRouter()

# v1.6 / v1.6.1 toy robustness: fixed scenario generation seeds (not trial seeds inside benchmark matrix).
# v1.6.1 extends from 8 to 24 instances for a larger descriptive sample (still toy-only).
DEFAULT_TOY_ROBUSTNESS_SEEDS: List[int] = [
    101,
    111,
    202,
    222,
    303,
    333,
    404,
    515,
    606,
    717,
    828,
    939,
    1049,
    1159,
    1269,
    1379,
    1489,
    1599,
    1709,
    1819,
    1929,
    2039,
    2149,
    2259,
]


def _experiment_with_inferred_fairness(exp: ExperimentRecord) -> ExperimentRecord:
    """Ensure stored config.fairness_classification matches v1.5.1 inference from hybrid trial evidence."""
    h_trials = [t for t in exp.trials if t.solver_kind == SolverKind.hybrid]
    inferred = infer_experiment_fairness_classification(exp.config, h_trials)
    if exp.config.fairness_classification == inferred:
        return exp
    return exp.model_copy(update={"config": exp.config.model_copy(update={"fairness_classification": inferred})})


class GenerateScenarioRequest(BaseModel):
    preset: str = "small"
    seed: int = 0
    density_target: float = 0.55
    compatibility_strength: float = 1.0
    objective_weights: ObjectiveWeights = ObjectiveWeights()


class RunExperimentRequest(BaseModel):
    scenario_id: str
    config: ExperimentConfig


class RunSolverRequest(BaseModel):
    scenario: Scenario
    config: SolverRunConfig


def _trial_seed(base_seed: int, trial_idx: int, policy: str, benchmark_preset: str = "custom") -> int:
    if benchmark_preset in BENCHMARK_MATRIX:
        seeds = BENCHMARK_MATRIX[benchmark_preset]["seeds"]
        return int(seeds[trial_idx % len(seeds)])
    return base_seed if policy == "fixed" else base_seed + trial_idx


def _calibrate_penalty_scale(scenario: Scenario, config: ExperimentConfig) -> tuple[float, list[dict[str, float]]]:
    sweep_cfg = config.penalty_sweep
    if not sweep_cfg.enabled:
        return config.common_budget.penalty_scale, []
    records = []
    best = None
    for cand in sweep_cfg.candidates:
        cfg = config.common_budget.model_copy()
        cfg.penalty_scale = float(cand)
        cfg.max_iterations = min(cfg.max_iterations, 20)
        cfg.max_time_seconds = min(cfg.max_time_seconds, 1.5)
        solver = HybridQuboSolver()
        t0 = time.perf_counter()
        sol, _, _ = solver.solve(scenario, cfg)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        overlap = float(sol.violation_breakdown.get("overlap_violations", 0))
        density = float(sol.violation_breakdown.get("density_violations", 0))
        density_gap = float(sol.density_metrics.get("density_gap", 0.0))
        rec = {
            "penalty_scale": float(cand),
            "feasible": float(1 if sol.feasible else 0),
            "objective": float(sol.objective),
            "violation_count": float(len(sol.violations)),
            "overlap_violations": overlap,
            "density_violations": density,
            "density_gap": density_gap,
            "runtime_ms": float(elapsed_ms),
        }
        records.append(rec)
        if sweep_cfg.selection_metric == "objective_only":
            score = (-rec["objective"],)
        else:
            # v1.3.1 scoring priority:
            # feasibility -> lowest density violations -> lowest overlap -> lowest total -> objective -> runtime
            score = (
                rec["feasible"],
                -rec["density_violations"],
                -rec["density_gap"],
                -rec["overlap_violations"],
                -rec["violation_count"],
                -rec["objective"],
                -rec["runtime_ms"],
            )
        if best is None or score > best[0]:
            best = (score, rec["penalty_scale"])
    return (best[1] if best else config.common_budget.penalty_scale), records


@router.post("/scenarios/generate")
def post_generate_scenario(req: GenerateScenarioRequest):
    scenario = generate_scenario(
        seed=req.seed,
        preset=req.preset,
        density_target=req.density_target,
        compatibility_strength=req.compatibility_strength,
        objective_weights=req.objective_weights,
    )
    save_scenario(scenario)
    return scenario


@router.get("/benchmarks/matrix")
def get_benchmark_matrix():
    return BENCHMARK_MATRIX


class ToyRobustnessSweepRequest(BaseModel):
    """v1.6: multi-instance toy study (single classical + hybrid run per scenario seed). Explicitly not `small`."""

    seeds: List[int] = Field(default_factory=lambda: list(DEFAULT_TOY_ROBUSTNESS_SEEDS))
    preset: str = "toy"
    density_target: float = 0.55
    strict_parity_mode: bool = True
    penalty_scale: float = 60.0
    study_label: str = "v1.6.1 toy robustness"
    # Relabeled mode only: clamp density into achievability band when allowed. Default off for hygiene parity with experiments.
    density_clamp_mode: Literal["off", "explicit_fallback"] = "off"


@router.get("/benchmarks/toy-robustness-default-seeds")
def get_toy_robustness_default_seeds():
    return {
        "seeds": DEFAULT_TOY_ROBUSTNESS_SEEDS,
        "note": "Scenario generation seeds for toy robustness sweep (v1.6.1: 24 fixed seeds; one geometry + one solver pair per seed).",
    }


@router.post("/benchmarks/toy-robustness-sweep")
def post_toy_robustness_sweep(req: ToyRobustnessSweepRequest):
    if req.preset != "toy":
        raise HTTPException(
            status_code=400,
            detail="v1.6 robustness sweep is implemented for preset=toy only (do not use for small).",
        )
    row = BENCHMARK_MATRIX.get("toy")
    if not row:
        raise HTTPException(status_code=400, detail="toy preset missing from benchmark matrix")
    fairness_label = (
        "repair-assisted approximate-comparable" if req.strict_parity_mode else "exploratory-only"
    )
    rows_out: List[Dict[str, Any]] = []
    for seed in req.seeds:
        scenario = generate_scenario(seed=seed, preset="toy", density_target=req.density_target)
        run_cfg = SolverRunConfig(
            max_time_seconds=float(row["max_time_seconds"]),
            max_iterations=int(row["max_iterations"]),
            seed=seed,
            penalty_scale=req.penalty_scale,
            strict_parity_mode=req.strict_parity_mode,
        )
        density_rep = apply_density_target_adjustment_if_valid(
            scenario, run_cfg, density_clamp_mode=req.density_clamp_mode
        )
        feats = compute_instance_features(scenario, run_cfg)
        t0 = time.perf_counter()
        c_sol, _, _ = CPSATSolver().solve(scenario, run_cfg)
        c_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        h_sol, _, _ = HybridQuboSolver().solve(scenario, run_cfg)
        h_ms = (time.perf_counter() - t0) * 1000
        density_summary = {
            "achievable_density_min": density_rep.get("achievable_density_min"),
            "achievable_density_max": density_rep.get("achievable_density_max"),
            "target_density_reported": density_rep.get("target_density"),
            "density_target_effective": float(scenario.density_target),
            "achievability_valid": density_rep.get("achievability_valid"),
            "target_inside_achievable_band": density_rep.get("target_inside_achievable_band"),
            "target_adjustment_applied": density_rep.get("target_adjustment_applied"),
            "candidate_truncation_risk_achievability": density_rep.get("candidate_truncation_risk"),
            "candidate_cap_used_achievability": density_rep.get("candidate_cap_used"),
        }
        rows_out.append(
            {
                "scenario_seed": seed,
                "scenario_id": scenario.id,
                "study_label": req.study_label,
                "fairness_classification": fairness_label,
                "density_achievability": density_summary,
                "features": feats,
                "classical": {
                    "feasible": c_sol.feasible,
                    "runtime_ms": c_ms,
                    "objective": c_sol.objective,
                    "overlap_violations": c_sol.violation_breakdown.get("overlap_violations", 0),
                    "density_violations": c_sol.violation_breakdown.get("density_violations", 0),
                },
                "hybrid": {
                    "feasible": h_sol.feasible,
                    "runtime_ms": h_ms,
                    "objective": h_sol.objective,
                    "overlap_violations": h_sol.violation_breakdown.get("overlap_violations", 0),
                    "density_violations": h_sol.violation_breakdown.get("density_violations", 0),
                },
                "difficulty": classify_instance_difficulty(c_sol.feasible, h_sol.feasible),
            }
        )
    numeric_keys = [
        "conflict_density",
        "inter_block_conflict_density",
        "occupancy_pressure_volume",
        "max_block_footprint_ratio_vs_smallest_sector",
        "candidates_total",
        "inter_block_conflict_count",
        "conflict_pair_count",
        "candidate_count_cv",
    ]
    contrast = feature_contrast_summary(rows_out, numeric_keys)
    robustness_table: List[Dict[str, Any]] = []
    for r in rows_out:
        f = r["features"]
        robustness_table.append(
            {
                "seed": r["scenario_seed"],
                "cand_total": f["candidates_total"],
                "conflict_density": round(float(f["conflict_density"]), 5),
                "inter_block_conflicts": int(f["inter_block_conflict_count"]),
                "occupancy_pressure": round(float(f["occupancy_pressure_volume"]), 4),
                "footprint_pressure": round(float(f["max_block_footprint_ratio_vs_smallest_sector"]), 4),
                "truncation_risk": f["candidate_truncation_risk"],
                "classical_feasible": r["classical"]["feasible"],
                "hybrid_feasible": r["hybrid"]["feasible"],
                "overlap_violations_classical": int(r["classical"]["overlap_violations"]),
                "overlap_violations_hybrid": int(r["hybrid"]["overlap_violations"]),
                "density_violations_classical": int(r["classical"]["density_violations"]),
                "density_violations_hybrid": int(r["hybrid"]["density_violations"]),
                "runtime_classical_ms": round(float(r["classical"]["runtime_ms"]), 2),
                "runtime_hybrid_ms": round(float(r["hybrid"]["runtime_ms"]), 2),
                "difficulty": r["difficulty"],
            }
        )
    return {
        "study_label": req.study_label,
        "preset": req.preset,
        "fairness_classification": fairness_label,
        "benchmark_budget": dict(row),
        "methodology": {
            "feature_definitions": (
                "See compute_instance_features docstring in backend/app/domain/instance_diagnostics.py"
            ),
            "sample_size": len(rows_out),
            "statistical_strength": (
                "Descriptive only: contrasts between easy vs hard subsets; small-n; not hypothesis-tested."
            ),
            "difficulty_rule": "easy: both feasible; hard: neither feasible; moderate: exactly one feasible",
            "solver_pair_per_instance": "one CP-SAT + one hybrid run per scenario seed (not repeated trials)",
        },
        "easy_vs_hard_feature_contrast": contrast,
        "instances": rows_out,
        "robustness_table": robustness_table,
    }


@router.post("/benchmarks/toy-robustness-sweep/deduplicate")
def post_toy_robustness_sweep_deduplicate(sweep: Dict[str, Any]):
    """
    v1.6.2 hygiene: cluster `instances` by layout fingerprint (candidate/conflict structural slice).
    Does not re-run solvers; pass a saved `robustness_sweep.json` body.
    """
    if not isinstance(sweep, dict) or "instances" not in sweep:
        raise HTTPException(
            status_code=400,
            detail="Body must be a full toy robustness sweep object including 'instances'.",
        )
    return deduplicate_robustness_sweep(sweep)


@router.get("/benchmarks/{preset}/methodology-template")
def get_methodology_template(preset: str):
    return methodology_template_for_preset(preset)


@router.post("/solvers/classical/run")
def post_run_classical(req: RunSolverRequest):
    solver = CPSATSolver()
    t0 = time.perf_counter()
    solution, progression, logs = solver.solve(req.scenario, req.config)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {
        "solver": solver.name,
        "backend_type": solver.backend_type,
        "elapsed_ms": elapsed_ms,
        "best_progression": progression,
        "solution": solution.model_dump(),
        "logs": logs,
    }


@router.post("/solvers/hybrid/run")
def post_run_hybrid(req: RunSolverRequest):
    solver = HybridQuboSolver()
    t0 = time.perf_counter()
    solution, progression, logs = solver.solve(req.scenario, req.config)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {
        "solver": solver.name,
        "backend_type": solver.backend_type,
        "elapsed_ms": elapsed_ms,
        "best_progression": progression,
        "solution": solution.model_dump(),
        "logs": logs,
    }


async def _run_trial_pair(exp: ExperimentRecord, trial_idx: int):
    scenario = exp.scenario
    cfg = exp.config
    run_cfg = cfg.common_budget.model_copy()
    run_cfg.seed = _trial_seed(cfg.common_budget.seed, trial_idx, cfg.seed_policy, cfg.benchmark_preset)

    c_solver = CPSATSolver()
    h_solver = HybridQuboSolver()

    async def run_classical():
        t0 = time.perf_counter()
        sol, prog, logs = c_solver.solve(scenario, run_cfg)
        return TrialResult(
            trial_index=trial_idx,
            solver_kind=SolverKind.classical,
            solver_name=c_solver.name,
            backend_type=c_solver.backend_type,
            seed=run_cfg.seed,
            elapsed_ms=(time.perf_counter() - t0) * 1000,
            objective=sol.objective,
            feasible=sol.feasible,
            violation_count=len(sol.violations),
            violation_breakdown=sol.violation_breakdown,
            best_progression=prog,
            solution=sol,
            logs=logs,
        )

    async def run_hybrid():
        t0 = time.perf_counter()
        sol, prog, logs = h_solver.solve(scenario, run_cfg)
        return TrialResult(
            trial_index=trial_idx,
            solver_kind=SolverKind.hybrid,
            solver_name=h_solver.name,
            backend_type=h_solver.backend_type,
            seed=run_cfg.seed,
            elapsed_ms=(time.perf_counter() - t0) * 1000,
            objective=sol.objective,
            feasible=sol.feasible,
            violation_count=len(sol.violations),
            violation_breakdown=sol.violation_breakdown,
            best_progression=prog,
            solution=sol,
            logs=logs,
        )

    if cfg.run_mode == "parallel":
        return await asyncio.gather(run_classical(), run_hybrid())
    return [await run_classical(), await run_hybrid()]


@router.post("/experiments/run")
async def post_run_experiment(req: RunExperimentRequest):
    scenario = load_scenario(req.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    run_cfg = req.config.common_budget.model_copy()
    selected_penalty_scale, sweep_records = _calibrate_penalty_scale(scenario, req.config)
    run_cfg.penalty_scale = selected_penalty_scale
    cfg = req.config.model_copy()
    cfg.common_budget = run_cfg

    if cfg.benchmark_preset in BENCHMARK_MATRIX:
        # Preset rows intentionally override repeats/time/iterations for matrix consistency.
        # Use benchmark_preset="custom" for fully explicit controlled diagnostics.
        row = BENCHMARK_MATRIX[cfg.benchmark_preset]
        cfg.repeats = int(row["repeats"])
        cfg.common_budget.max_time_seconds = float(row["max_time_seconds"])
        cfg.common_budget.max_iterations = int(row["max_iterations"])
        cfg.seed_policy = "fixed"

    density_requested = float(scenario.density_target)
    density_report = density_achievability_report(scenario, cfg.common_budget)
    attach_benchmark_hygiene_metadata(
        density_report,
        density_target_requested=density_requested,
        density_clamp_applied=False,
        density_target_adjusted_value=None,
    )
    density_report["target_adjustment_applied"] = False
    density_report["target_adjusted_for_feasibility"] = density_requested

    if cfg.density_clamp_mode == "explicit_fallback" and density_report.get("adjustment_allowed") and not density_report.get(
        "target_inside_achievable_band", True
    ):
        # Clamp is explicit-only and metadata is relabeled; default benchmark mode keeps requested target unchanged.
        lo = float(density_report["achievable_density_min"])
        hi = float(density_report["achievable_density_max"])
        if lo <= hi:
            scenario.density_target = min(max(float(scenario.density_target), lo), hi)
            density_report = density_achievability_report(scenario, cfg.common_budget)
            attach_benchmark_hygiene_metadata(
                density_report,
                density_target_requested=density_requested,
                density_clamp_applied=True,
                density_target_adjusted_value=float(scenario.density_target),
            )
            density_report["target_adjustment_applied"] = True
            density_report["target_adjusted_for_feasibility"] = float(scenario.density_target)
            density_report["density_clamp_mode_applied"] = "explicit_fallback"
    elif not density_report.get("achievability_valid", False):
        density_report["target_adjustment_reason"] = "achievability_invalid_no_adjustment"

    exp = ExperimentRecord(
        id=f"exp_{uuid4().hex[:10]}",
        scenario=scenario,
        config=cfg,
        status="running",
        selected_penalty_scale=selected_penalty_scale,
        penalty_sweep_results=sweep_records,
        density_achievability=density_report,
    )
    save_experiment(exp)
    trials = []
    for i in range(cfg.repeats):
        pair = await _run_trial_pair(exp, i)
        trials.extend(pair)
        exp.trials = trials
        exp.updated_at = datetime.now(timezone.utc)
        save_experiment(exp)

    exp.status = "completed"
    if exp.trials:
        h_trials = [t for t in exp.trials if t.solver_kind == SolverKind.hybrid]
        if h_trials:
            exp.config.fairness_classification = infer_experiment_fairness_classification(exp.config, h_trials)
    exp.updated_at = datetime.now(timezone.utc)
    save_experiment(exp)
    return {"experiment_id": exp.id, "status": exp.status, "trial_count": len(exp.trials)}


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    exp = load_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.get("/experiments/{experiment_id}/results")
def get_experiment_results(experiment_id: str):
    exp = load_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    c_trials = [t for t in exp.trials if t.solver_kind == SolverKind.classical]
    h_trials = [t for t in exp.trials if t.solver_kind == SolverKind.hybrid]
    stats = compute_experiment_stats(c_trials, h_trials, exp.config)
    # Instance-level structural KPIs computed on the shared candidate graph (no solver run).
    instance_features = compute_instance_features(exp.scenario, exp.config.common_budget)
    return {
        "experiment": _experiment_with_inferred_fairness(exp),
        "stats": stats,
        "instance_features": instance_features,
    }


@router.get("/experiments/{experiment_id}/export")
def export_experiment(experiment_id: str, format: str = "json"):
    exp = load_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    c_trials = [t for t in exp.trials if t.solver_kind == SolverKind.classical]
    h_trials = [t for t in exp.trials if t.solver_kind == SolverKind.hybrid]
    stats = compute_experiment_stats(c_trials, h_trials, exp.config)
    exp_out = _experiment_with_inferred_fairness(exp)
    payload: Dict[str, Any] = {"experiment": exp_out.model_dump(mode="json"), "stats": stats.model_dump(mode="json")}
    if format == "csv":
        lines = [
            "trial_index,solver_kind,seed,elapsed_ms,objective,feasible,violations,backend_type,"
            "placement_geometry_valid,solver_certified_geometry,"
            "overlap_violations,boundary_violations,assignment_violations,activation_consistency_violations,density_violations,other_violations"
        ]
        for t in exp.trials:
            b = t.violation_breakdown
            sol = t.solution
            geom_valid = bool(sol.placement_geometry_valid) if sol else False
            certified = bool(
                sol
                and sol.placement_geometry_valid
                and not bool(sol.solver_metadata.get("placement_extraction_invalid", False))
            )
            lines.append(
                f"{t.trial_index},{t.solver_kind},{t.seed},{t.elapsed_ms:.4f},{t.objective:.6f},{int(t.feasible)},{t.violation_count},{t.backend_type},"
                f"{int(geom_valid)},{int(certified)},"
                f"{b.get('overlap_violations',0)},{b.get('boundary_violations',0)},{b.get('assignment_violations',0)},"
                f"{b.get('activation_consistency_violations',0)},{b.get('density_violations',0)},{b.get('other_violations',0)}"
            )
        return {"format": "csv", "content": "\n".join(lines)}
    payload["density_benchmark_metadata"] = exp.density_achievability
    payload["instance_features"] = compute_instance_features(exp.scenario, exp.config.common_budget)
    return {"format": "json", "content": json.dumps(payload, indent=2)}
