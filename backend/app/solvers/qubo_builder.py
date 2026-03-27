from __future__ import annotations

"""Builds the shared QUBO representation over the candidate map."""

from typing import Dict

import dimod

from app.domain.formulation import build_conflicts, generate_candidates, objective_cost
from app.domain.instance_diagnostics import candidate_grid_params
from app.domain.models import Scenario, SolverRunConfig


def build_qubo(scenario: Scenario, config: SolverRunConfig) -> tuple[dimod.BinaryQuadraticModel, Dict[str, object]]:
    """
    Build QUBO over candidate selection variables.
    Hard CP constraints are mirrored here as penalties (approximate by construction).
    """
    linear = {}
    quadratic = {}
    offset = 0.0
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
    for b in scenario.blocks:
        for c in cand_map[b.id]:
            linear[c.placement_id] = 0.0
    yvars = {}
    for s in scenario.sectors:
        y = f"y_{s.id}"
        yvars[s.id] = y
        linear[y] = scenario.objective_weights.active_sectors

    penalty = float(config.penalty_scale)

    # Exactly-one assignment per block over candidate placements.
    for b in scenario.blocks:
        vars_b = [c.placement_id for c in cand_map[b.id]]
        for v in vars_b:
            linear[v] = linear.get(v, 0.0) - penalty
        for i in range(len(vars_b)):
            linear[vars_b[i]] = linear.get(vars_b[i], 0.0) + penalty
            for j in range(i + 1, len(vars_b)):
                quadratic[(vars_b[i], vars_b[j])] = quadratic.get((vars_b[i], vars_b[j]), 0.0) + 2.0 * penalty
        offset += penalty

    # Explicit non-overlap and same-block conflict penalties.
    # In strict parity mode, bias harder toward feasibility to reduce overlap leakage.
    min_conflict_multiplier = 10.0 if strict else 1.0
    conflict_penalty = penalty * max(min_conflict_multiplier, config.conflict_penalty_multiplier)
    for a, b in build_conflicts(cand_map):
        quadratic[(a, b)] = quadratic.get((a, b), 0.0) + conflict_penalty

    # Sector activation consistency: x <= y  -> penalty * x * (1-y)
    activation_penalty = penalty * max(1.0, config.conflict_penalty_multiplier / 2.0)
    for b in scenario.blocks:
        for c in cand_map[b.id]:
            x = c.placement_id
            y = yvars[c.sector_id]
            linear[x] += activation_penalty
            quadratic[(x, y)] = quadratic.get((x, y), 0.0) - activation_penalty

    # Shared linear objective costs from candidate features.
    btype = {b.id: b.block_type.value for b in scenario.blocks}
    for bid, cands in cand_map.items():
        for c in cands:
            linear[c.placement_id] += objective_cost(c, scenario, btype[bid], config.strict_parity_mode)

    bqm = dimod.BinaryQuadraticModel(linear, quadratic, offset, dimod.BINARY)
    return bqm, {"candidates": cand_map, "yvars": yvars}
