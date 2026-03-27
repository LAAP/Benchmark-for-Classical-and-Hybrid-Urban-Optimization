from app.domain.instance_diagnostics import (
    apply_density_target_adjustment_if_valid,
    classify_instance_difficulty,
    compute_instance_features,
    feature_contrast_summary,
)
from app.domain.models import SolverRunConfig
from app.domain.scenario_generator import generate_scenario


def test_compute_instance_features_keys_and_sanity():
    scenario = generate_scenario(seed=42, preset="toy", density_target=0.55)
    cfg = SolverRunConfig(strict_parity_mode=True, max_time_seconds=3.0, max_iterations=30, seed=42)
    apply_density_target_adjustment_if_valid(scenario, cfg)
    f = compute_instance_features(scenario, cfg)
    assert f["candidates_total"] > 0
    assert f["conflict_pair_count"] >= f["inter_block_conflict_count"]
    assert 0.0 <= f["conflict_density"] <= 1.0
    assert f["occupancy_pressure_volume"] >= 0.0


def test_classify_difficulty():
    assert classify_instance_difficulty(True, True) == "easy"
    assert classify_instance_difficulty(False, False) == "hard"
    assert classify_instance_difficulty(True, False) == "moderate"


def test_feature_contrast_summary():
    rows = [
        {
            "difficulty": "easy",
            "features": {"conflict_density": 0.1, "candidates_total": 100},
        },
        {
            "difficulty": "hard",
            "features": {"conflict_density": 0.3, "candidates_total": 50},
        },
    ]
    c = feature_contrast_summary(rows, ["conflict_density", "candidates_total"])
    assert any(x["feature"] == "conflict_density" for x in c)
    cd = next(x for x in c if x["feature"] == "conflict_density")
    assert cd["mean_easy"] == 0.1 and cd["mean_hard"] == 0.3
