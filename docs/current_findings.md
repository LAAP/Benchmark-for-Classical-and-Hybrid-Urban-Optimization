# Current Findings

> [!WARNING]
> This repository does **not** demonstrate quantum advantage.  
> Most solver comparisons are **approximate**, not exact.  
> Some runs are diagnostic only and should not be treated as benchmark evidence.  
> `small` currently appears hard/infeasible under the present discrete formulation.

## Toy Status

- Toy demo is usable for controlled internal demonstration.
- Toy is currently the safer regime for controlled benchmark comparisons.
- Hygiene metadata, fairness classification, and export evidence are functioning.
- Interpretation should remain approximate-comparison (not exact parity).
- Note: older toy robustness evidence and current live demo runs are not always identical, even for the same seed. The effective benchmark instance is defined by the *current candidate graph* (candidate enumeration/cap/grid + conflicts + hygiene rules), not by seed number alone. A seed that was previously “easy” may not remain easy after candidate-generation changes.

## Small Status

- Structural comparability for density has improved significantly (non-degenerate bands, explicit target metadata).
- Candidate-space artifact mitigation (sector balancing + moderate cap/stride diagnostics) broadened manifold coverage.
- For tested diagnostic seed/config paths, CP-SAT still returns infeasible, suggesting persistent hard/infeasible structure under current discrete assumptions.

## What Is Scientifically Established

- Fairness labels are now explicit and enforce conservative interpretation.
- Silent density target adjustment is disabled by default.
- Non-certified CP-SAT runs no longer export fake geometry.
- Structural diagnostics can distinguish artifact-driven collapse from persistent infeasibility.
- In tested small diagnostics, infeasibility persists after non-trivial manifold broadening.

## What Is Still Uncertain

- How broadly current small-seed conclusions generalize beyond tested diagnostics.
- Whether alternative formulation choices (not yet adopted) could recover feasible small regimes.
- Whether hybrid behavior under different backend conditions materially changes conclusions.

## Regime Map

- **Toy:** usable benchmark regime, with caveats about approximate parity and backend differences.
- **Small:** structurally comparable on density, but currently hard/infeasible under the current discrete candidate/conflict formulation in tested diagnostics.

## Safe Claims vs Unsafe Claims

### Safe Claims
- The benchmark is now substantially more hygiene-aware and reproducible.
- Many earlier interpretation hazards have been reduced.
- Small-scale infeasibility in tested diagnostics is not explained solely by trivial candidate starvation.

### Unsafe Claims
- “Quantum advantage has been demonstrated.”
- “Exact solver parity is achieved.”
- “All small instances are infeasible.”
- “Any single diagnostic run is publication-grade benchmark evidence by itself.”

## Interpretation Guidance For Collaborators

When reviewing results:
- check fairness class first,
- check `placement_geometry_valid` / `solver_certified_geometry`,
- check density comparability flags (`benchmark_comparable`, degeneracy, target-inside-band),
- distinguish diagnostic studies from benchmark studies.

See `docs/reproducibility.md` for safe run protocol and `docs/glossary.md` for terminology.
