export type ObjectiveWeights = {
  active_sectors: number;
  skyline_height: number;
  compactness: number;
  density_deviation: number;
  compatibility: number;
  accessibility: number;
};

export type GenerateScenarioRequest = {
  preset: string;
  seed: number;
  density_target: number;
  compatibility_strength: number;
  objective_weights: ObjectiveWeights;
};

export type Scenario = {
  id: string;
  seed: number;
  blocks: Array<{
    id: string;
    width: number;
    depth: number;
    min_height: number;
    max_height: number;
    block_type: string;
  }>;
  sectors: Array<{ id: string; width: number; depth: number; max_height: number }>;
};

export type ExperimentConfig = {
  repeats: number;
  classical_solver: string;
  hybrid_solver: string;
  run_mode: "parallel" | "sequential";
  seed_policy: "fixed" | "increment";
  benchmark_preset: "parity_tiny" | "toy" | "small" | "custom";
  fairness_classification:
    | "exact-comparable"
    | "approximate-comparable"
    | "strong-approximate-comparable"
    | "repair-assisted approximate-comparable"
    | "exploratory-only";
  penalty_sweep: {
    enabled: boolean;
    candidates: number[];
    selection_metric: "feasibility_then_objective" | "objective_only";
  };
  density_clamp_mode?: "off" | "explicit_fallback";
  common_budget: {
    max_time_seconds: number;
    max_iterations: number;
    seed: number;
    warm_start: boolean;
    penalty_scale: number;
    strict_parity_mode: boolean;
    sector_balanced_candidates?: boolean;
    max_candidates_per_block_override?: number | null;
    stride_xy_override?: number | null;
  };
};

export type InstanceFeatures = {
  grid?: { stride_xy?: number; stride_z?: number; max_candidates_per_block?: number };
  candidates_total?: number;
  candidates_per_block?: Record<string, number>;
  conflict_pair_count?: number;
  inter_block_conflict_count?: number;
  conflict_density?: number;
  inter_block_conflict_density?: number;
  occupancy_pressure_volume?: number;
  candidate_truncation_risk?: boolean;
  // Optional backend fields (not required by UI).
  [k: string]: unknown;
};
