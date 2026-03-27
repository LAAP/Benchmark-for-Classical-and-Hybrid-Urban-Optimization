from app.domain.metrics import evaluate_solution
from app.domain.models import Placement
from app.domain.scenario_generator import generate_scenario


def test_scenario_is_deterministic_with_same_seed():
    s1 = generate_scenario(seed=42, preset="toy")
    s2 = generate_scenario(seed=42, preset="toy")
    assert [b.model_dump() for b in s1.blocks] == [b.model_dump() for b in s2.blocks]
    assert [s.model_dump() for s in s1.sectors] == [s.model_dump() for s in s2.sectors]


def test_metrics_detects_missing_assignments():
    scenario = generate_scenario(seed=1, preset="toy")
    placements = [
        Placement(block_id=scenario.blocks[0].id, sector_id=scenario.sectors[0].id, orientation=0, x=0, y=0, z=0, height=5)
    ]
    sol = evaluate_solution(scenario, placements)
    assert not sol.feasible
    assert any(v.startswith("missing_assignment:") for v in sol.violations)
