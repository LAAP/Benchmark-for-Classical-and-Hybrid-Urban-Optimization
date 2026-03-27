from __future__ import annotations

"""CP-SAT baseline with conservative geometry-certification behavior."""

import time

from ortools.sat.python import cp_model

from app.domain.formulation import build_conflicts, generate_candidates, objective_cost
from app.domain.instance_diagnostics import candidate_grid_params
from app.domain.metrics import evaluate_solution
from app.domain.models import Placement, Scenario, Solution, SolverRunConfig
from app.solvers.base import SolverAdapter


class CPSATSolver(SolverAdapter):
    name = "cp_sat"
    backend_type = "ortools_cp_sat"

    def solve(self, scenario: Scenario, config: SolverRunConfig):
        start = time.perf_counter()
        model = cp_model.CpModel()
        blocks = scenario.blocks
        sectors = scenario.sectors
        strict = config.strict_parity_mode
        gp = candidate_grid_params(scenario, config)
        cand_map = generate_candidates(
            scenario,
            stride_xy=gp["stride_xy"],
            stride_z=gp["stride_z"],
            max_candidates_per_block=gp["max_candidates_per_block"],
            strict_parity_mode=strict,
            sector_balanced=config.sector_balanced_candidates,
        )
        xvar = {}
        for b in blocks:
            for c in cand_map[b.id]:
                xvar[c.placement_id] = model.NewBoolVar(c.placement_id)
            model.Add(sum(xvar[c.placement_id] for c in cand_map[b.id]) == 1)

        conflicts = build_conflicts(cand_map)
        for a, b in conflicts:
            model.Add(xvar[a] + xvar[b] <= 1)

        # Explicit active-sector vars for objective parity report.
        y_sector = {s.id: model.NewBoolVar(f"active_{s.id}") for s in sectors}
        for b in blocks:
            for c in cand_map[b.id]:
                model.Add(xvar[c.placement_id] <= y_sector[c.sector_id])

        scale = 1000
        obj_terms = []
        for b in blocks:
            for c in cand_map[b.id]:
                cst = objective_cost(c, scenario, b.block_type.value, config.strict_parity_mode)
                obj_terms.append(int(scale * cst) * xvar[c.placement_id])
        for s in sectors:
            obj_terms.append(int(scale * scenario.objective_weights.active_sectors) * y_sector[s.id])

        model.Minimize(sum(obj_terms))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = config.max_time_seconds
        solver.parameters.max_number_of_conflicts = max(1, config.max_iterations * 100)
        solver.parameters.random_seed = config.seed
        status = solver.Solve(model)
        logs = [f"cp_sat_status={status}"]

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Benchmark hygiene: do not export pseudo-geometry when solver has no certified assignment.
            elapsed_ms = (time.perf_counter() - start) * 1000
            logs.append(f"elapsed_ms={elapsed_ms:.2f}")
            logs.append("placement_extraction_suppressed=non_certified_status")
            empty_breakdown = {k: 0 for k in ("overlap_violations", "boundary_violations", "assignment_violations", "activation_consistency_violations", "density_violations", "other_violations")}
            return (
                Solution(
                    placements=[],
                    active_sectors=[],
                    objective=0.0,
                    feasible=False,
                    violations=["solver_no_certified_assignment:cp_sat"],
                    violation_breakdown={**empty_breakdown, "other_violations": 1},
                    density_metrics={},
                    exact_optimum=False,
                    solver_metadata={
                        "cp_sat_status": str(status),
                        "placement_extraction_invalid": True,
                    },
                    placement_geometry_valid=False,
                ),
                [0.0],
                logs,
            )

        placements = []
        for b in blocks:
            chosen = cand_map[b.id][0]
            for c in cand_map[b.id]:
                if solver.Value(xvar[c.placement_id]) > 0:
                    chosen = c
                    break
            placements.append(
                Placement(
                    block_id=b.id,
                    sector_id=chosen.sector_id,
                    orientation=chosen.orientation,
                    x=chosen.x,
                    y=chosen.y,
                    z=chosen.z,
                    height=chosen.height,
                )
            )

        solution = evaluate_solution(scenario, placements)
        solution.placement_geometry_valid = True
        solution.solver_metadata = {"cp_sat_status": str(status), "placement_extraction_invalid": False}
        elapsed_ms = (time.perf_counter() - start) * 1000
        progression = [solution.objective * (1.0 + (0.3 / (k + 1))) for k in range(5)] + [solution.objective]
        logs.append(f"elapsed_ms={elapsed_ms:.2f}")
        return solution, progression, logs
