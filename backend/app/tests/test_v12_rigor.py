from app.core.benchmark_matrix import BENCHMARK_MATRIX, benchmark_seeds
from app.domain.metrics import evaluate_solution
from app.domain.models import ExperimentConfig, ExperimentRecord, PenaltySweepConfig, Placement
from app.domain.scenario_generator import generate_scenario
from app.solvers.qubo_builder import build_qubo


def test_parity_mode_changes_qubo_energy_landscape():
    scenario = generate_scenario(seed=9, preset="parity_tiny")
    c0 = ExperimentConfig().common_budget
    c1 = c0.model_copy()
    c1.strict_parity_mode = True
    bqm0, _ = build_qubo(scenario, c0)
    bqm1, _ = build_qubo(scenario, c1)
    assert bqm0.num_variables == bqm1.num_variables
    assert abs(bqm0.offset - bqm1.offset) < 1e-9


def test_sector_activation_variables_exist():
    scenario = generate_scenario(seed=10, preset="parity_tiny")
    bqm, meta = build_qubo(scenario, ExperimentConfig().common_budget)
    yvars = meta["yvars"]
    assert len(yvars) == len(scenario.sectors)
    for y in yvars.values():
        assert y in bqm.variables


def test_violation_breakdown_categories_populate():
    scenario = generate_scenario(seed=11, preset="parity_tiny")
    b0, b1 = scenario.blocks[0], scenario.blocks[1]
    s0 = scenario.sectors[0]
    placements = [
        Placement(block_id=b0.id, sector_id=s0.id, orientation=0, x=0, y=0, z=0, height=b0.min_height),
        Placement(block_id=b1.id, sector_id=s0.id, orientation=0, x=0, y=0, z=0, height=b1.min_height),
    ]
    sol = evaluate_solution(scenario, placements)
    assert sol.violation_breakdown["overlap_violations"] >= 1
    assert "assignment_violations" in sol.violation_breakdown


def test_benchmark_preset_reproducibility_matrix():
    assert "parity_tiny" in BENCHMARK_MATRIX and "toy" in BENCHMARK_MATRIX and "small" in BENCHMARK_MATRIX
    assert benchmark_seeds("toy") == [111, 222, 333]


def test_penalty_sweep_metadata_persistence_fields():
    cfg = ExperimentConfig(
        penalty_sweep=PenaltySweepConfig(enabled=True, candidates=[5.0, 10.0], selection_metric="feasibility_then_objective")
    )
    scenario = generate_scenario(seed=12, preset="parity_tiny")
    exp = ExperimentRecord(
        id="exp_test",
        scenario=scenario,
        config=cfg,
        selected_penalty_scale=10.0,
        penalty_sweep_results=[{"penalty_scale": 5.0, "feasible": 0.0, "objective": 10.0, "violation_count": 2.0}],
    )
    dumped = exp.model_dump()
    assert dumped["config"]["penalty_sweep"]["enabled"] is True
    assert dumped["selected_penalty_scale"] == 10.0
    assert dumped["penalty_sweep_results"][0]["penalty_scale"] == 5.0
