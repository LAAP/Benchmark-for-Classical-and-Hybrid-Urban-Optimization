from app.stats.small_feasibility_diagnosis import diagnose_seed, run_small_feasibility_diagnosis


def test_diagnose_seed_has_core_fields():
    r = diagnose_seed(123, density_target=0.55)
    assert r["seed"] == 123
    assert "structural_features_strict" in r
    assert "single_effective_sector_packing" in r
    assert "block_pair_same_sector_stats" in r
    assert isinstance(r["block_pair_same_sector_stats"], list)
    assert len(r["block_pair_same_sector_stats"]) == 66  # C(12,2)


def test_run_aggregate_three_seeds():
    out = run_small_feasibility_diagnosis(seeds=[123, 234, 345], density_target=0.55)
    assert len(out["per_seed"]) == 3
    assert "recommendation" in out
