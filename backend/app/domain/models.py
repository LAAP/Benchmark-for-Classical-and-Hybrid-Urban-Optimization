from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

DensityClampMode = Literal["off", "explicit_fallback"]


class BlockType(str, Enum):
    residential = "residential"
    commercial = "commercial"
    office = "office"
    civic = "civic"
    green = "green"


class SolverKind(str, Enum):
    classical = "classical"
    hybrid = "hybrid"


class HybridBackend(str, Enum):
    dwave_hybrid = "dwave_hybrid"
    simulated_annealing_fallback = "simulated_annealing_fallback"


class FairnessClass(str, Enum):
    exact_comparable = "exact-comparable"
    approximate_comparable = "approximate-comparable"
    strong_approximate_comparable = "strong-approximate-comparable"
    repair_assisted_approximate_comparable = "repair-assisted approximate-comparable"
    exploratory_only = "exploratory-only"


class ObjectiveWeights(BaseModel):
    active_sectors: float = 1.0
    skyline_height: float = 1.0
    compactness: float = 1.0
    density_deviation: float = 1.0
    compatibility: float = 1.0
    accessibility: float = 0.5


class Block(BaseModel):
    id: str
    width: int
    depth: int
    min_height: int
    max_height: int
    block_type: BlockType
    density_weight: float = 1.0
    compatibility_tags: List[str] = Field(default_factory=list)


class Sector(BaseModel):
    id: str
    width: int
    depth: int
    max_height: int
    capacity: int
    context: Dict[str, float] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str
    seed: int
    density_target: float
    compatibility_strength: float
    objective_weights: ObjectiveWeights
    blocks: List[Block]
    sectors: List[Sector]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Placement(BaseModel):
    block_id: str
    sector_id: str
    orientation: Literal[0, 1]
    x: int
    y: int
    z: int
    height: int


class Solution(BaseModel):
    placements: List[Placement]
    active_sectors: List[str]
    objective: float
    feasible: bool
    violations: List[str] = Field(default_factory=list)
    violation_breakdown: Dict[str, int] = Field(default_factory=dict)
    density_metrics: Dict[str, float] = Field(default_factory=dict)
    exact_optimum: bool = False
    # Hybrid/QUBO provenance for fairness reporting (classical runs leave default).
    solver_metadata: Dict[str, object] = Field(default_factory=dict)
    # False when CP-SAT (or other solvers) did not certify a feasible assignment and placements must not be interpreted geometrically.
    placement_geometry_valid: bool = True


class SolverRunConfig(BaseModel):
    max_time_seconds: float = 10.0
    max_iterations: int = 500
    seed: int = 0
    warm_start: bool = False
    penalty_scale: float = 10.0
    conflict_penalty_multiplier: float = 6.0
    strict_parity_mode: bool = False
    # Candidate-space hygiene: round-robin enumeration across sectors under the same cap.
    sector_balanced_candidates: bool = False
    # Optional local override (diagnostic): per-block candidate cap used by all solvers/diagnostics when set.
    max_candidates_per_block_override: Optional[int] = None
    # Optional local override (diagnostic): grid stride in x/y for candidate placement enumeration.
    stride_xy_override: Optional[int] = None


class PenaltySweepConfig(BaseModel):
    enabled: bool = False
    candidates: List[float] = Field(default_factory=lambda: [5.0, 10.0, 20.0, 30.0])
    selection_metric: Literal["feasibility_then_objective", "objective_only"] = "feasibility_then_objective"


class TrialResult(BaseModel):
    trial_index: int
    solver_kind: SolverKind
    solver_name: str
    backend_type: str
    seed: int
    elapsed_ms: float
    objective: float
    feasible: bool
    violation_count: int
    violation_breakdown: Dict[str, int] = Field(default_factory=dict)
    best_progression: List[float] = Field(default_factory=list)
    solution: Optional[Solution] = None
    logs: List[str] = Field(default_factory=list)


class ExperimentConfig(BaseModel):
    repeats: int = 5
    classical_solver: str = "cp_sat"
    hybrid_solver: str = "qubo_hybrid"
    run_mode: Literal["parallel", "sequential"] = "parallel"
    common_budget: SolverRunConfig = Field(default_factory=SolverRunConfig)
    seed_policy: Literal["fixed", "increment"] = "increment"
    benchmark_preset: Literal["parity_tiny", "toy", "small", "custom"] = "custom"
    fairness_classification: FairnessClass = FairnessClass.approximate_comparable
    penalty_sweep: PenaltySweepConfig = Field(default_factory=PenaltySweepConfig)
    # Benchmark hygiene: default preserves requested scenario.density_target; use explicit_fallback only for relabeled clamp experiments.
    density_clamp_mode: DensityClampMode = "off"


class ExperimentRecord(BaseModel):
    id: str
    scenario: Scenario
    config: ExperimentConfig
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trials: List[TrialResult] = Field(default_factory=list)
    selected_penalty_scale: Optional[float] = None
    penalty_sweep_results: List[Dict[str, float]] = Field(default_factory=list)
    density_achievability: Dict[str, object] = Field(default_factory=dict)


class SummaryStats(BaseModel):
    mean: float
    median: float
    std: float
    ci95_low: float
    ci95_high: float


class SolverSummary(BaseModel):
    solver_name: str
    backend_type: str
    runtime: SummaryStats
    objective: SummaryStats
    feasibility_rate: float
    best_objective: float
    violation_mean: float
    violation_breakdown_mean: Dict[str, float] = Field(default_factory=dict)


class ExperimentStats(BaseModel):
    classical: SolverSummary
    hybrid: SolverSummary
    paired_p_value: Optional[float] = None
    paired_effect_size: Optional[float] = None
    fairness_report: Dict[str, object] = Field(default_factory=dict)
