# Benchmark Glossary

## strict parity mode
Configuration mode that aligns candidate variables and key objective terms across solver paths.  
It improves methodological consistency but does not make CP-SAT and QUBO mathematically identical.

## benchmark_comparable
Boolean metadata flag indicating that density target comparison is structurally valid:
- achievable band is valid and non-degenerate,
- requested target lies inside the achievable band.

## benchmark_non_comparable
Inverse of `benchmark_comparable`.  
Indicates the run should not be treated as clean benchmark evidence for density-target comparison.

## achievability_degenerate
True when the candidate-derived achievable density band collapses to near-zero width (or invalid).  
Degenerate bands weaken comparability claims.

## benchmark_structurally_infeasible_target
Flag indicating structural mismatch between requested target and candidate-achievable density conditions (including degenerate/out-of-band scenarios).

## density_clamp_mode
Mode controlling density target handling:
- `off` (default): requested target preserved, no silent adjustment.
- `explicit_fallback`: target may be clamped into achievable band when allowed; must be interpreted as relabeled fallback behavior.

## placement_geometry_valid
Per-solution flag indicating whether returned placements are geometrically interpretable/certified for analysis.

In the UI this is presented as **Decoded layout is valid**.

## solver_certified_geometry
Export-level conservative indicator (CSV) that geometry is valid and not marked as extraction-invalid by solver metadata.

In the UI this is presented as **Certified layout**.

## repair-assisted approximate-comparable
Fairness class for strict-parity hybrid runs where decode behavior includes feasibility-first / repair-assisted traits.  
Still approximate, not exact parity.

## density target
Requested target density for the scenario. Solver outputs are evaluated against this target (or explicitly adjusted target in fallback mode).

## sector-balanced enumeration
Candidate-generation strategy that cycles across sectors under cap, reducing first-sector saturation artifacts.

## height-stratified candidate generation
Strict-parity candidate strategy that preserves representative low/mid/high heights under cap to avoid height-collapse artifacts.

## candidate truncation risk
Indicator that one or more blocks hit the candidate cap; candidate manifold may be incomplete relative to full discretized space.

## candidate graph
The effective discrete benchmark instance: candidate placements + conflict edges under the current enumeration/grid/cap/hygiene rules.

Two runs with the same seed can differ if the candidate graph construction rules changed between versions.

## instance hardness metrics
Structural metrics computed on the shared candidate graph (for example `conflict_density`, `inter_block_conflict_density`, occupancy pressure, candidate totals, truncation risk).

They describe instance pressure; they are not direct solver-quality scores.

## not evaluated / dash (`—`)
UI convention indicating the metric is not evaluated because no certified valid layout was available for that solver run.

Typical examples: objective or violation counts shown as `—` when solver-certified geometry is absent.
