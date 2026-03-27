import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from app.api.routes import export_experiment
from app.domain.density_diagnostics import attach_benchmark_hygiene_metadata, density_achievability_report
from app.domain.instance_diagnostics import apply_density_target_adjustment_if_valid
from app.domain.models import ExperimentConfig, ExperimentRecord, Scenario, SolverRunConfig
from app.domain.scenario_generator import generate_scenario
from app.solvers.classical_cpsat import CPSATSolver


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_degenerate_band_flags_achievability_degenerate():
    rep = {
        "achievable_density_min": 0.0,
        "achievable_density_max": 0.0,
        "target_inside_achievable_band": False,
        "achievability_valid": True,
        "target_density": 0.55,
    }
    attach_benchmark_hygiene_metadata(rep, density_target_requested=0.55)
    assert rep["achievability_degenerate"] is True
    assert rep["adjustment_allowed"] is False
    assert rep["benchmark_comparable"] is False
    assert rep["benchmark_non_comparable"] is True


def test_non_degenerate_out_of_band_adjustment_allowed():
    rep = {
        "achievable_density_min": 0.1,
        "achievable_density_max": 0.5,
        "target_inside_achievable_band": False,
        "achievability_valid": True,
        "target_density": 0.99,
    }
    attach_benchmark_hygiene_metadata(rep, density_target_requested=0.99)
    assert rep["achievability_degenerate"] is False
    assert rep["adjustment_allowed"] is True
    assert rep["benchmark_out_of_band"] is True


def test_experiment_default_no_silent_clamp_small_seed_123():
    scenario = generate_scenario(seed=123, preset="small", density_target=0.55)
    before = float(scenario.density_target)
    cfg = SolverRunConfig(
        strict_parity_mode=True,
        max_time_seconds=4.0,
        max_iterations=35,
        seed=123,
    )
    rep = apply_density_target_adjustment_if_valid(scenario, cfg, density_clamp_mode="off")
    assert scenario.density_target == before
    assert rep["target_adjustment_applied"] is False


def test_explicit_fallback_clamps_when_band_non_degenerate():
    scenario = generate_scenario(seed=101, preset="parity_tiny", density_target=0.99)
    cfg = SolverRunConfig(strict_parity_mode=True, max_time_seconds=2.0, max_iterations=40, seed=101)
    raw = density_achievability_report(scenario, cfg)
    attach_benchmark_hygiene_metadata(raw, density_target_requested=0.99)
    if not (raw.get("adjustment_allowed") and raw.get("benchmark_out_of_band")):
        pytest.skip("fixture density does not trigger clamp for this seed")
    s2 = deepcopy(scenario)
    rep = apply_density_target_adjustment_if_valid(s2, cfg, density_clamp_mode="explicit_fallback")
    assert rep["target_adjustment_applied"] is True
    lo, hi = float(rep["achievable_density_min"]), float(rep["achievable_density_max"])
    assert lo <= s2.density_target <= hi


def test_infeasible_cpsat_suppresses_placements():
    path = _project_root() / "evidence" / "reduced_risk_small_verification" / "results.json"
    if not path.is_file():
        pytest.skip("stored diagnostic reduced-risk small bundle not present")
    data = json.loads(path.read_text())["experiment"]
    scenario = Scenario.model_validate(data["scenario"])
    scenario.density_target = 0.55
    cfg = SolverRunConfig(
        max_time_seconds=4.0,
        max_iterations=35,
        seed=123,
        strict_parity_mode=True,
        penalty_scale=60.0,
    )
    sol, _, logs = CPSATSolver().solve(scenario, cfg)
    if not any("INFEASIBLE" in line for line in logs):
        pytest.skip("diagnostic scenario no longer proves INFEASIBLE under current CP-SAT path")
    assert sol.placement_geometry_valid is False
    assert len(sol.placements) == 0
    assert sol.solver_metadata.get("placement_extraction_invalid") is True
    assert not any(str(v).startswith("overlap:") for v in sol.violations)


def test_export_json_includes_density_benchmark_metadata():
    exp = ExperimentRecord(
        id="exp_unit_test_export",
        scenario=generate_scenario(seed=1, preset="parity_tiny", density_target=0.5),
        config=ExperimentConfig(repeats=1, density_clamp_mode="off"),
        status="completed",
        density_achievability={
            "density_target_requested": 0.5,
            "density_target_stored_for_solve": 0.5,
            "density_clamp_applied": False,
            "benchmark_comparable": True,
        },
        trials=[],
    )
    with patch("app.api.routes.load_experiment", return_value=exp):
        wrapped = export_experiment(exp.id)
    content = json.loads(wrapped["content"])
    assert "density_benchmark_metadata" in content
    assert content["density_benchmark_metadata"]["density_target_requested"] == 0.5
