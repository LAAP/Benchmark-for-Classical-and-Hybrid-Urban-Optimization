from app.domain.models import ExperimentConfig, FairnessClass, SolverKind, SolverRunConfig, TrialResult
from app.stats.analysis import compute_experiment_stats, infer_experiment_fairness_classification


def _hybrid_trial(**kwargs) -> TrialResult:
    base = dict(
        trial_index=0,
        solver_kind=SolverKind.hybrid,
        solver_name="qubo_hybrid",
        backend_type="simulated_annealing_fallback",
        seed=1,
        elapsed_ms=1.0,
        objective=1.0,
        feasible=True,
        violation_count=0,
        logs=[],
    )
    base.update(kwargs)
    return TrialResult(**base)


def test_infer_repair_assisted_when_feasibility_first_log():
    cfg = ExperimentConfig(common_budget=SolverRunConfig(strict_parity_mode=True), benchmark_preset="toy")
    t = _hybrid_trial(logs=["decode=feasibility_first_greedy"])
    assert infer_experiment_fairness_classification(cfg, [t]) == FairnessClass.repair_assisted_approximate_comparable


def test_infer_strong_approximate_legacy_hybrid_no_markers():
    cfg = ExperimentConfig(common_budget=SolverRunConfig(strict_parity_mode=True), benchmark_preset="toy")
    t = _hybrid_trial(logs=[], solution=None)
    assert infer_experiment_fairness_classification(cfg, [t]) == FairnessClass.strong_approximate_comparable


def test_infer_exploratory_without_strict_parity():
    cfg = ExperimentConfig(common_budget=SolverRunConfig(strict_parity_mode=False), benchmark_preset="toy")
    t = _hybrid_trial(logs=["decode=feasibility_first_greedy"])
    assert infer_experiment_fairness_classification(cfg, [t]) == FairnessClass.exploratory_only


def test_stats_never_emits_exact_comparable_for_hybrid_success():
    cfg = ExperimentConfig(common_budget=SolverRunConfig(strict_parity_mode=True), benchmark_preset="toy")
    c = TrialResult(
        trial_index=0,
        solver_kind=SolverKind.classical,
        solver_name="cp_sat",
        backend_type="ortools_cp_sat",
        seed=1,
        elapsed_ms=1.0,
        objective=1.0,
        feasible=True,
        violation_count=0,
    )
    h = _hybrid_trial(trial_index=0, logs=["decode=feasibility_first_greedy"])
    stats = compute_experiment_stats([c], [h], cfg)
    assert stats.fairness_report["comparison_type"] != "exact-comparable"
    assert stats.fairness_report["comparison_type"] == "repair-assisted approximate-comparable"
