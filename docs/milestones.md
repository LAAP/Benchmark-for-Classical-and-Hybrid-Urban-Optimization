# Development Milestones

This file records major methodological milestones in chronological order.

## 1) Fairness labeling improvements
- Introduced explicit fairness classes and inference logic from trial evidence.
- Clarified that CP-SAT vs QUBO-hybrid remains approximate in this repository.

## 2) Density consistency fix
- Added explicit density-achievability reporting (min/max band, inside-band status, degeneracy, margins).
- Improved consistency between requested and stored target metadata.

## 3) Benchmark hygiene fix
- Default `density_clamp_mode` set to `off` (no silent clamping).
- Added explicit fallback mode for relabeled clamp behavior.
- Prevented non-certified CP-SAT outputs from being interpreted as valid geometry.

## 4) Height-stratified candidate generation
- Strict parity candidate generation now allocates cap across representative heights (low/mid/high).
- Reduced degenerate density-band artifacts caused by cap-first truncation.

## 5) Sector-balanced enumeration
- Added round-robin candidate enumeration across sectors under cap.
- Removed major single-sector collapse behavior in small diagnostics.

## 6) Cap increase diagnostics
- Performed controlled cap broadening diagnostics (e.g., 24->48->64->80) on small seed diagnostics.
- Observed manifold broadening and conflict-density shifts.

## 7) Stride counterfactuals
- Tested stride changes with controlled cap settings.
- Found that finer stride can remain masked under tight cap; broader caps reveal richer manifold effects.

## 8) Toy robustness sweep
- Added toy-only robustness sweep and dedup tooling for descriptive regime studies.

## 9) Small feasibility diagnosis
- Added targeted structural diagnosis scripts for small-scale infeasibility interpretation.
- Current diagnostics indicate persistent hardness/infeasibility under present discrete formulation for tested seed paths.

For narrative interpretation, see `docs/current_findings.md`.  
For definitions, see `docs/glossary.md`.
