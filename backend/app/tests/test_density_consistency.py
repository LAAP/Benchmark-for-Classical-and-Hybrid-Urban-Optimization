from app.domain.density_diagnostics import density_achievability_report
from app.domain.models import SolverRunConfig
from app.domain.scenario_generator import generate_scenario


def test_achievable_band_sane_range_and_order():
    scenario = generate_scenario(seed=999, preset="toy", density_target=0.5)
    rep = density_achievability_report(scenario, SolverRunConfig(strict_parity_mode=True))
    assert rep["achievability_valid"] is True
    assert 0.0 <= rep["achievable_density_min"] <= 1.0
    assert 0.0 <= rep["achievable_density_max"] <= 1.0
    assert rep["achievable_density_min"] <= rep["achievable_density_max"]


def test_target_and_band_same_scale():
    scenario = generate_scenario(seed=999, preset="toy", density_target=0.5)
    rep = density_achievability_report(scenario, SolverRunConfig(strict_parity_mode=True))
    assert 0.0 <= rep["target_density"] <= 1.0
    assert 0.0 <= rep["achievable_density_min"] <= 1.0
    assert 0.0 <= rep["achievable_density_max"] <= 1.0


def test_degenerate_band_only_when_structurally_forced():
    scenario = generate_scenario(seed=101, preset="parity_tiny", density_target=0.5)
    rep = density_achievability_report(scenario, SolverRunConfig(strict_parity_mode=True))
    # Degenerate can happen, but should remain valid and non-negative.
    assert rep["achievability_valid"] is True
    assert rep["achievable_density_min"] >= 0.0
    assert rep["achievable_density_max"] >= 0.0
