from copy import deepcopy

from app.domain.robustness_fingerprint import (
    fingerprint_definition_text,
    sweep_instance_layout_fingerprint,
)
from app.stats.robustness_dedup import deduplicate_robustness_sweep


def _minimal_instance(seed: int, conflict_pair_count: int = 100) -> dict:
    return {
        "scenario_seed": seed,
        "scenario_id": f"s_{seed}",
        "features": {
            "grid": {"stride_xy": 3, "stride_z": 2, "max_candidates_per_block": 24},
            "candidates_per_block": {"B0": 5, "B1": 5},
            "candidates_total": 10,
            "conflict_pair_count": conflict_pair_count,
            "inter_block_conflict_count": 40,
            "intra_block_exclusion_pairs": 10,
            "conflict_density": 0.1,
            "inter_block_conflict_density": 0.05,
            "occupancy_pressure_volume": 0.01,
            "max_block_footprint_ratio_vs_smallest_sector": 0.2,
            "blocks_per_sector": 2.0,
            "mean_block_height_span_levels": 3.0,
            "candidate_truncation_risk": False,
        },
        "classical": {
            "feasible": True,
            "runtime_ms": 1.0,
            "overlap_violations": 0,
            "density_violations": 0,
        },
        "hybrid": {
            "feasible": True,
            "runtime_ms": 2.0,
            "overlap_violations": 0,
            "density_violations": 0,
        },
        "difficulty": "easy",
    }


def test_fingerprint_stable_for_same_structural_slice():
    a = _minimal_instance(1, 100)
    b = deepcopy(a)
    b["scenario_seed"] = 99
    b["classical"]["feasible"] = False
    b["hybrid"]["feasible"] = False
    b["difficulty"] = "hard"
    assert sweep_instance_layout_fingerprint(a) == sweep_instance_layout_fingerprint(b)


def test_fingerprint_differs_when_conflict_count_changes():
    a = _minimal_instance(1, 100)
    b = _minimal_instance(2, 101)
    assert sweep_instance_layout_fingerprint(a) != sweep_instance_layout_fingerprint(b)


def test_dedup_groups_identical_layouts_representative_min_seed():
    sweep = {
        "study_label": "t",
        "instances": [
            _minimal_instance(50, 200),
            _minimal_instance(10, 200),
            _minimal_instance(20, 300),
        ],
    }
    out = deduplicate_robustness_sweep(sweep)
    assert out["raw_instance_count"] == 3
    assert out["unique_layout_count"] == 2
    assert out["duplication_factor_raw_per_unique"] == 1.5
    assert len(out["duplicate_groups"]) == 1
    assert out["duplicate_groups"][0]["seeds"] == [10, 50]
    reps = {r["representative_seed"] for r in out["dedup_table"]}
    assert 10 in reps
    assert 20 in reps


def test_fingerprint_definition_text_nonempty():
    assert "sha256" in fingerprint_definition_text().lower()
