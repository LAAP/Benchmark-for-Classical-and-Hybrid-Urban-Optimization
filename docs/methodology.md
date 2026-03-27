# Benchmark Methodology

## Benchmark Philosophy

This project prioritizes **transparent, reproducible, and falsifiable** solver comparisons over performance marketing.

Core principles:
- Shared scenario generation and shared evaluation logic.
- Explicit metadata about fairness class, geometry validity, and benchmark comparability.
- Conservative interpretation when formulation or backend differences remain.

## Solver Comparison Rules

Each paired trial should, by default:
- use the same scenario instance,
- use the same trial seed policy,
- use the same high-level budget fields (`max_time_seconds`, `max_iterations`),
- be evaluated by the same post-solve checker.

However, CP-SAT and QUBO are not mathematically identical encodings in this repository, so comparisons remain mostly approximate.

## Why Comparisons Are Approximate (Not Exact)

CP-SAT:
- hard constraints with exact Boolean/linear feasibility semantics.

Hybrid QUBO:
- penalty-encoded constraints,
- sample-based optimization,
- decode heuristics (`feasibility_first_greedy`, optional overlap repair behavior).

Therefore, strict parity can align candidate universe and objective terms, but not fully remove methodological differences.

See also: `docs/glossary.md` for precise term definitions.

## What “Repair-Assisted Approximate-Comparable” Means

A run is labeled `repair-assisted approximate-comparable` when:
- strict parity mode is on, and
- hybrid trial evidence indicates feasibility-first decode and/or sample activation fallback.

Interpretation:
- still a useful comparison class,
- still **not** exact parity,
- results should not be described as exact solver-to-solver equivalence.

## Why Silent Target Clamping Was Removed

Earlier workflows could silently move requested density targets into feasible bands.  
That makes comparisons difficult to interpret because the solved target may differ from the requested target.

Current default:
- `density_clamp_mode="off"` (no silent adjustment),
- all achievability and comparability metadata exported explicitly.

Clamp is only allowed in explicit fallback mode and should be treated as a relabeled diagnostic condition.

## Why Infeasible CP-SAT Runs Must Not Produce Fake Geometry

If CP-SAT returns non-certified status (`INFEASIBLE`, etc.), exporting placements as if valid can create false geometric conclusions.

Current behavior:
- infeasible/non-certified CP-SAT runs suppress placement extraction,
- `placement_geometry_valid=false`,
- `solver_no_certified_assignment:cp_sat` is recorded.

This is a benchmark hygiene requirement, not a UI preference.

## Why Toy and Small Behave Differently

`toy`:
- typically lower structural pressure and more usable benchmark behavior.

`small`:
- larger and denser conflict structure under current discrete assumptions,
- historically sensitive to candidate truncation and ordering artifacts,
- now structurally cleaner but still often infeasible under tested configurations.

## What Was Learned From Recent Methodological Interventions

### Density consistency and hygiene fixes
- improved interpretability and removed silent-target ambiguity.

### Height-stratified strict candidates
- prevented degenerate density-band collapse due to cap saturating a single height level.

### Sector-balanced enumeration
- removed first-sector saturation artifact at low caps.

### Cap increases (diagnostic progression)
- broadened candidate manifold and reduced conflict densities in some settings.
- did not, by itself, recover CP-SAT feasibility in tested small-seed diagnostics.

### Stride counterfactuals
- finer `stride_xy` required sufficient cap to affect sampled manifold.
- once manifold broadened, CP-SAT remained infeasible in tested one-seed diagnostics.

## Methodological Bottom Line

Current evidence supports:
- improved benchmark hygiene and comparability metadata,
- reduced artifact-driven failure modes,
- persistent small-scale infeasibility under present discrete packing formulation for tested diagnostics.

It does **not** support:
- quantum advantage claims,
- exact parity claims between CP-SAT and QUBO-hybrid.

For current empirical status, read `docs/current_findings.md`.
