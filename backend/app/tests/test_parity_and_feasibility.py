from app.domain.formulation import CandidatePlacement, overlap_3d
from app.domain.metrics import evaluate_solution
from app.domain.models import Placement, SolverRunConfig
from app.domain.scenario_generator import generate_scenario
from app.solvers.classical_cpsat import CPSATSolver
from app.solvers.hybrid_solver import HybridQuboSolver


def test_overlap_3d_detection():
    a = CandidatePlacement("a", "B0", "S0", 0, 0, 0, 0, 4, 3, 3)
    b = CandidatePlacement("b", "B1", "S0", 0, 2, 2, 1, 4, 3, 3)
    c = CandidatePlacement("c", "B2", "S0", 0, 5, 5, 5, 2, 2, 2)
    assert overlap_3d(a, b)
    assert not overlap_3d(a, c)


def test_feasibility_check_catches_overlap():
    scenario = generate_scenario(seed=10, preset="parity_tiny")
    b0 = scenario.blocks[0]
    b1 = scenario.blocks[1]
    sec = scenario.sectors[0]
    placements = [
        Placement(block_id=b0.id, sector_id=sec.id, orientation=0, x=0, y=0, z=0, height=b0.min_height),
        Placement(block_id=b1.id, sector_id=sec.id, orientation=0, x=0, y=0, z=0, height=b1.min_height),
    ]
    sol = evaluate_solution(scenario, placements)
    assert not sol.feasible
    assert any(v.startswith("overlap:") for v in sol.violations)


def test_solver_output_comparability():
    scenario = generate_scenario(seed=77, preset="parity_tiny")
    cfg = SolverRunConfig(max_time_seconds=2, max_iterations=50, seed=77, penalty_scale=20)
    c_sol, _, _ = CPSATSolver().solve(scenario, cfg)
    h_sol, _, _ = HybridQuboSolver().solve(scenario, cfg)
    assert len(c_sol.placements) == len(scenario.blocks)
    assert len(h_sol.placements) == len(scenario.blocks)
    assert isinstance(c_sol.objective, float)
    assert isinstance(h_sol.objective, float)


def test_hybrid_decode_prefers_non_overlapping_choice_when_available():
    scenario = generate_scenario(seed=7, preset="parity_tiny")
    b0 = scenario.blocks[0]
    b1 = scenario.blocks[1]
    # Build tiny candidate map with one conflicting option and one safe option for B1.
    c0 = CandidatePlacement("p0", b0.id, "S0", 0, 0, 0, 0, b0.min_height, b0.width, b0.depth)
    c1_conflict = CandidatePlacement("p1_conflict", b1.id, "S0", 0, 0, 0, 0, b1.min_height, b1.width, b1.depth)
    c1_safe = CandidatePlacement("p1_safe", b1.id, "S0", 0, 10, 10, 0, b1.min_height, b1.width, b1.depth)
    cand_map = {b.id: [] for b in scenario.blocks}
    cand_map[b0.id] = [c0]
    cand_map[b1.id] = [c1_conflict, c1_safe]
    for idx, b in enumerate(scenario.blocks[2:], start=2):
        cand_map[b.id] = [
            CandidatePlacement(f"p{idx}", b.id, "S1", 0, 20 + idx, 20 + idx, 0, b.min_height, b.width, b.depth)
        ]
    sample = {"p0": 1, "p1_conflict": 1, "p1_safe": 0}
    chosen = HybridQuboSolver._decode_with_overlap_repair(scenario, SolverRunConfig(strict_parity_mode=True), cand_map, sample)
    assert chosen[b1.id].placement_id == "p1_safe"
