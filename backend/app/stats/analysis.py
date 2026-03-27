from __future__ import annotations

"""Statistical aggregation + fairness interpretation layer for experiment exports."""

from statistics import mean, median, stdev
from typing import Dict, List, Sequence

import numpy as np
from scipy import stats as scipy_stats

from app.domain.models import ExperimentConfig, ExperimentStats, FairnessClass, SolverSummary, SummaryStats, TrialResult


def hybrid_trial_is_repair_assisted(t: TrialResult) -> bool:
    """True if hybrid used feasibility-first greedy decode and/or sample activation fallback (non-literal assignment)."""
    meta = (t.solution.solver_metadata if t.solution else {}) or {}
    if meta.get("decode_mode") == "feasibility_first_greedy":
        return True
    if meta.get("sample_activation_fallback"):
        return True
    return any(
        "decode=feasibility_first_greedy" in log
        or "decode=feasibility_first_overlap_repair" in log
        or "decode=feasibility_first" in log
        for log in t.logs
    )


def infer_experiment_fairness_classification(
    config: ExperimentConfig | None, hybrid_trials: List[TrialResult]
) -> FairnessClass:
    """
    v1.5.1 rules (documented in fairness_report.classification_logic):
    - Hybrid QUBO in this codebase always uses soft (penalty) constraint encoding -> never exact-comparable vs CP-SAT.
    - Feasibility-first greedy decode and/or sample-activation fallback -> repair-assisted approximate-comparable.
    - Otherwise strict parity + hybrid -> strong-approximate-comparable (soft QUBO, lighter decode policy).
    - Non-strict -> exploratory-only.
    """
    if config is None:
        return FairnessClass.approximate_comparable
    strict = bool(config.common_budget.strict_parity_mode)
    if not strict:
        return FairnessClass.exploratory_only
    if not hybrid_trials:
        return FairnessClass.approximate_comparable
    if any(hybrid_trial_is_repair_assisted(t) for t in hybrid_trials):
        return FairnessClass.repair_assisted_approximate_comparable
    return FairnessClass.strong_approximate_comparable


def _summary(values: Sequence[float]) -> SummaryStats:
    vals = [float(v) for v in values]
    if not vals:
        return SummaryStats(mean=0.0, median=0.0, std=0.0, ci95_low=0.0, ci95_high=0.0)
    if len(vals) == 1:
        return SummaryStats(mean=vals[0], median=vals[0], std=0.0, ci95_low=vals[0], ci95_high=vals[0])

    m = mean(vals)
    sd = stdev(vals)
    t = scipy_stats.t.ppf(0.975, len(vals) - 1)
    sem = sd / np.sqrt(len(vals))
    return SummaryStats(mean=m, median=median(vals), std=sd, ci95_low=m - t * sem, ci95_high=m + t * sem)


def _solver_summary(trials: List[TrialResult]) -> SolverSummary:
    runtimes = [t.elapsed_ms for t in trials]
    objectives = [t.objective for t in trials]
    feasibility = [1.0 if t.feasible else 0.0 for t in trials]
    violations = [t.violation_count for t in trials]
    breakdown_mean: Dict[str, float] = {}
    if trials:
        keys = set()
        for t in trials:
            keys.update(t.violation_breakdown.keys())
        for k in sorted(keys):
            breakdown_mean[k] = float(mean(t.violation_breakdown.get(k, 0) for t in trials))
    return SolverSummary(
        solver_name=trials[0].solver_name if trials else "unknown",
        backend_type=trials[0].backend_type if trials else "unknown",
        runtime=_summary(runtimes),
        objective=_summary(objectives),
        feasibility_rate=float(mean(feasibility)) if feasibility else 0.0,
        best_objective=min(objectives) if objectives else 0.0,
        violation_mean=float(mean(violations)) if violations else 0.0,
        violation_breakdown_mean=breakdown_mean,
    )


def compute_experiment_stats(
    classical_trials: List[TrialResult], hybrid_trials: List[TrialResult], config: ExperimentConfig | None = None
) -> ExperimentStats:
    classical = _solver_summary(classical_trials)
    hybrid = _solver_summary(hybrid_trials)

    paired_p_value = None
    paired_effect_size = None
    if len(classical_trials) >= 3 and len(classical_trials) == len(hybrid_trials):
        c = np.array([t.objective for t in classical_trials], dtype=float)
        h = np.array([t.objective for t in hybrid_trials], dtype=float)
        _, p = scipy_stats.ttest_rel(c, h)
        diff = c - h
        sd = np.std(diff, ddof=1) if len(diff) > 1 else 0.0
        d = (np.mean(diff) / sd) if sd > 0 else 0.0
        paired_p_value = float(p)
        paired_effect_size = float(d)

    strict = bool(config.common_budget.strict_parity_mode) if config else False
    hybrid_trials_list = hybrid_trials or []
    inferred = infer_experiment_fairness_classification(config, hybrid_trials_list)
    fairness_level = inferred.value
    repair_assisted = any(hybrid_trial_is_repair_assisted(t) for t in hybrid_trials_list)
    uses_soft_qubo = bool(hybrid_trials_list)  # all hybrid paths use penalty-encoded constraints in this repo

    # Constraint-level diagnostics for interpretability.
    c_fail = classical.violation_breakdown_mean
    h_fail = hybrid.violation_breakdown_mean
    top_c = sorted(c_fail.items(), key=lambda kv: kv[1], reverse=True)[:2]
    top_h = sorted(h_fail.items(), key=lambda kv: kv[1], reverse=True)[:2]
    c_budget_risk = classical.runtime.mean > ((config.common_budget.max_time_seconds * 1000) * 0.9) if config else False
    h_budget_risk = hybrid.runtime.mean > ((config.common_budget.max_time_seconds * 1000) * 0.9) if config else False

    c_by_trial = {t.trial_index: t for t in classical_trials}
    h_by_trial = {t.trial_index: t for t in hybrid_trials}
    common_idx = sorted(set(c_by_trial.keys()) & set(h_by_trial.keys()))
    same_density_fail = []
    density_gap_by_solver = {"classical": [], "hybrid": []}
    for idx in common_idx:
        ct = c_by_trial[idx]
        ht = h_by_trial[idx]
        cd = ct.violation_breakdown.get("density_violations", 0)
        hd = ht.violation_breakdown.get("density_violations", 0)
        if cd > 0 and hd > 0:
            same_density_fail.append(idx)
        if ct.solution and ct.solution.density_metrics:
            density_gap_by_solver["classical"].append(float(ct.solution.density_metrics.get("density_gap", 0.0)))
        if ht.solution and ht.solution.density_metrics:
            density_gap_by_solver["hybrid"].append(float(ht.solution.density_metrics.get("density_gap", 0.0)))

    fairness_report = {
        "comparison_type": fairness_level,
        "fairness_classification_inferred": fairness_level,
        "classification_logic": [
            "exact-comparable is not assigned to classical vs hybrid QUBO runs: CP-SAT uses hard constraints; QUBO uses penalties.",
            "repair-assisted approximate-comparable applies when hybrid trials use feasibility-first greedy decode (decode_mode=feasibility_first_greedy) and/or sample_activation_fallback, or matching log markers.",
            "strong-approximate-comparable applies under strict parity with hybrid but without recorded repair-assisted decode (legacy runs).",
            "exploratory-only applies when strict_parity_mode is false.",
        ],
        "hybrid_methodology_flags": {
            "uses_soft_qubo_penalties": uses_soft_qubo,
            "repair_assisted_decode": repair_assisted,
            "exact_solver_parity_claim": False,
        },
        "solver_mode": "strict_parity_mode" if strict else "default_mode",
        "objective_differences": [
            "Both use shared candidate linear terms skyline/compactness/density deviation.",
            "QUBO includes penalty-enforced activation consistency; CP-SAT encodes it as hard implications.",
            "Energy objective in QUBO may include residual penalty influence."
        ],
        "constraint_differences": [
            "Both include exactly-one assignment and pairwise non-overlap over shared candidates.",
            "CP-SAT constraints are hard; QUBO constraints rely on calibrated penalties.",
        ],
        "formulation_differences": [
            "Both solvers share discrete candidate placement variables (sector,x,y,z,orientation,height).",
            "CP-SAT enforces non-overlap as hard linear constraints; QUBO enforces via quadratic penalties.",
            "Sector activation variables are explicit in both; QUBO ties x->y via penalties."
        ],
        "backend_differences": [
            "Classical uses OR-Tools CP-SAT branch-and-bound + SAT search.",
            "Hybrid uses D-Wave hybrid sampler when available, otherwise simulated annealing fallback."
        ],
        "penalty_based_approximations": [
            "QUBO penalty scaling may admit low-penalty infeasible samples before post-checking.",
        ],
        "discretization_effects": [
            "Candidate-grid discretization (stride/max candidates) approximates continuous placement.",
        ],
        "parity_claim": "Strict mode aligns candidate sets and terms; hybrid remains penalty-encoded with non-literal decode, so claims must stay approximate.",
        "interpretation_guidance": (
            "only exploratory evidence"
            if fairness_level == FairnessClass.exploratory_only.value
            else (
                "approximate comparison (repair-assisted decode; not literal QUBO placement or hard-constraint parity)"
                if fairness_level == FairnessClass.repair_assisted_approximate_comparable.value
                else (
                    "approximate comparison (soft QUBO penalties; decode not equivalent to CP-SAT branch-and-bound)"
                    if fairness_level == FairnessClass.strong_approximate_comparable.value
                    else "approximate comparison (paired solvers; formulation/backends differ)"
                )
            )
        ),
        "constraint_diagnostics": {
            "classical_top_failures": top_c,
            "hybrid_top_failures": top_h,
            "classical_failure_driver": "budget-related" if c_budget_risk else "formulation-related",
            "hybrid_failure_driver": "budget-related" if h_budget_risk else "formulation-related",
            "same_failure_pattern": [k for k, _ in top_c if any(k == hk for hk, _ in top_h)],
            "density_failure_same_trials": same_density_fail,
            "density_gap_mean": {
                "classical": float(np.mean(density_gap_by_solver["classical"])) if density_gap_by_solver["classical"] else 0.0,
                "hybrid": float(np.mean(density_gap_by_solver["hybrid"])) if density_gap_by_solver["hybrid"] else 0.0,
            },
            "density_failure_reasoning": (
                "shared density target tension and discretization effects"
                if same_density_fail
                else "solver-specific behavior dominates"
            ),
        },
        "density_achievability_note": (
            "Experiments default to density_clamp_mode=off: requested density is preserved; see experiment.density_achievability "
            "for benchmark_comparable / achievability_degenerate / benchmark_out_of_band. "
            "Clamp only runs in explicit_fallback mode (relabeled)."
 ),
    }

    return ExperimentStats(
        classical=classical,
        hybrid=hybrid,
        paired_p_value=paired_p_value,
        paired_effect_size=paired_effect_size,
        fairness_report=fairness_report,
    )
