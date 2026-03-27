# Urban Optimization Benchmark: Classical vs Hybrid QUBO

If you are new to this repository, read these files first:
1. `README.md`
2. `docs/methodology.md`
3. `docs/current_findings.md`

> [!WARNING]
> This repository does **not** demonstrate quantum advantage.  
> Most solver comparisons are **approximate**, not exact parity.  
> Some runs are diagnostic only and should not be treated as benchmark evidence.  
> `small`-scale results currently indicate a hard/infeasible regime under the present discrete formulation.

## Project Summary

This repository implements a reproducible benchmarking framework for comparing:
- a **classical** solver (`OR-Tools CP-SAT`), and
- a **hybrid QUBO** pipeline (D-Wave hybrid when available, otherwise simulated annealing fallback),

on the same discretized urban placement instances.

The goal is methodological: build fairer, better-instrumented comparisons with explicit metadata about what is (and is not) comparable. This repository is a benchmark/diagnostic framework, not proof of quantum advantage.

## Sharing / Quick Orientation for Collaborators

This repository is a benchmarking framework for comparing a classical CP-SAT baseline and a hybrid QUBO-style workflow for urban-design optimization experiments.

A major part of the work so far has focused on making the benchmark scientifically safe to interpret, including fairness labels, density-achievability handling, certification flags, and structural diagnostics.

This repository does **not** demonstrate quantum advantage, and most solver comparisons remain approximate rather than exact.

At present, the `toy` regime is usable with caveats, while the `small` regime is best understood as a hard diagnostic regime under the current discrete formulation.

Start here:
1. `README.md`
2. `docs/methodology.md`
3. `docs/current_findings.md`

What this project currently supports:
- reproducible paired runs with explicit fairness, geometry, and hygiene metadata,
- controlled diagnostic studies that help separate structural issues from solver behavior.

What this project does not currently support:
- exact parity claims between CP-SAT and hybrid QUBO,
- quantum-advantage claims,
- broad generalization from a single diagnostic run.

## What the Benchmark Compares

- Shared seeded scenario generation (`toy`, `small`, etc.)
- Shared discrete candidate placement universe (`sector, x, y, z, orientation, height`)
- Shared post-solve evaluation (`feasible`, violation breakdown, density metrics)
- Exported trial-level metadata (runtime, backend, logs, geometry-validity flags, fairness labels)

## Current Project Status

- Core API, storage, and dashboard are implemented.
- Benchmark hygiene updates are implemented:
  - no silent density clamping in default benchmark mode,
  - explicit density-achievability metadata,
  - no fake CP-SAT geometry on infeasible/non-certified statuses.
- Candidate-space diagnostics have been extended (height stratification, sector-balanced enumeration, cap/stride counterfactuals).
- The toy demo exists and is usable for controlled internal demonstration (with caveats).
- Toy comparisons remain approximate, not exact parity.
- `small` is structurally improved but still infeasible/hard under the current discrete formulation for tested diagnostics.

## Key Methodological Findings So Far

- Fairness labels now explicitly represent approximate-comparison levels.
- Density target handling is transparent and auditable.
- Candidate starvation artifacts were reduced (sector balancing + moderate cap broadening).
- For tested `small` seed 123, CP-SAT remains infeasible even after meaningful manifold broadening, suggesting non-trivial packing hardness in the current formulation.

## Safe Interpretation (What This Repo Does NOT Prove)

- It does **not** prove quantum advantage.
- It does **not** provide exact classical-vs-quantum parity.
- It does **not** show that all `small` instances are equivalent; current strong conclusions are seed/config dependent.
- It does **not** support interpreting every run as benchmark evidence; some runs are explicitly diagnostic.

## Repository Structure

- `backend/`
  - `app/api/routes.py`: scenario, experiment, export, and toy robustness endpoints
  - `app/domain/`: scenario models, formulation, metrics, diagnostics
  - `app/solvers/`: CP-SAT + hybrid QUBO pipeline
  - `app/stats/`: fairness analysis, methodology templates, diagnostic scripts
  - `app/tests/`: unit tests for parity/hygiene/diagnostics
- `frontend/`
  - Next.js dashboard for scenario/config/run inspection
- `evidence/`
  - JSON/CSV artifacts from benchmark and diagnostic runs
- `docs/`
  - Methodology, findings, reproducibility guide, glossary, milestones

## Setup Instructions

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional (for D-Wave backend instead of fallback):

```bash
export DWAVE_API_TOKEN="your_token"
```

### Frontend (optional for diagnostics)

```bash
cd frontend
npm install
npm run dev
```

## How To Run Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

## How To Run Frontend

Frontend is optional for methodology and paper diagnostics (backend exports are sufficient).  
If needed:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

## Toy Demo UI (Internal)

The frontend is configured as a **toy-only research/demo dashboard** for controlled runs and interpretation checks.

> [!IMPORTANT]
> **Toy-only research demo.** Comparisons are **approximate**, not exact parity.  
> This repository does **not** demonstrate quantum advantage.  
> Interpret **benchmark readiness** and **certification/layout validity** before comparing KPI outcomes.

### How to use the demo (quick)

1. Start backend (example on a fresh port):

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8011
```

2. Start frontend pointing at that backend:

```bash
cd frontend
NEXT_PUBLIC_API_BASE="http://localhost:8011" npm run dev -- --port 3003
```

3. Open the dashboard: `http://localhost:3003`

Read results in this order:
- **Benchmark readiness** (benchmark-comparable vs diagnostic-only vs non-comparable)
- **Certification / layout validity** (`solver_certified_geometry`, `placement_geometry_valid`)
- Then interpret **KPI outcomes** (objective/runtime/violations)

Dashboard elements include:
- benchmark readiness + fairness classification,
- certification flags (`Certified layout`, `Decoded layout is valid`),
- KPI comparison + instance hardness metrics,
- plain-language interpretation support,
- live solver activity cards while a run is executing.

Input meaning (quick):
- **Toy seed**: selects one predefined toy benchmark case (different seeds can be easier or harder).
- **Density target**: desired density level (lower = looser/less dense; higher = tighter/more dense).
- **Strict parity**: stricter shared candidate setup for both methods; more controlled comparison, often harder instances.

KPI meaning (quick):
- **Feasible**: better if true.
- **Certified layout**: better if true; safe to interpret as layout.
- **Decoded layout is valid**: better if true; decoded geometry passes checks.
- **Objective**: lower is usually better within comparable/certified runs.
- **Overlap violations**: lower is better; `0` is best.
- **Density violations**: lower is better; `0` is best.
- **`—` (dash)**: metric not evaluated because no certified valid layout was available.

> [!WARNING]
> No quantum-advantage claim is supported.  
> Most solver comparisons remain approximate (not exact parity).  
> A visible hybrid layout can still be infeasible.  
> No classical layout does not mean the app is broken; it often means no certified feasible assignment was found.  
> Older toy evidence and current live runs may differ for the same seed because the effective candidate graph changed over time.

What to use it for:
- run one controlled toy experiment,
- inspect fairness and benchmark-comparability metadata,
- compare classical vs hybrid outcomes side by side,
- inspect KPI-style benchmark signals across validity, quality, efficiency, and instance hardness (structural metrics),
- review certification flags (`placement_geometry_valid`, `solver_certified_geometry`) before interpreting placements.

What not to use it for:
- small-mode benchmarking claims,
- winner-style comparisons,
- quantum-advantage narratives.

In the demo UI, pay special attention to:
- **Benchmark Status / Metadata** panel (comparability and clamp flags),
- **Benchmark KPIs** section (readiness banner + validity/quality/efficiency/hardness KPIs),
- **Solver result panels** (feasibility + certification),
- **Interpretation panel** (plain-language summary with caveats).

### Troubleshooting (frontend)

If the frontend renders as raw unstyled HTML, or you see stale Next.js chunk/module errors (for example `Cannot find module './819.js'`), clear `.next` and restart:

```bash
cd frontend
rm -rf .next
npm run dev -- --port 3000
```

If the issue persists, reinstall frontend dependencies:

```bash
cd frontend
rm -rf .next node_modules package-lock.json
npm install
npm run dev -- --port 3000
```

## How To Run Tests

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest -q
```

## How To Run Toy Experiments

Example (single controlled toy run):

1) Generate scenario:

```bash
curl -sS -X POST "http://127.0.0.1:8000/scenarios/generate" \
  -H "Content-Type: application/json" \
  -d '{"preset":"toy","seed":111,"density_target":0.55}'
```

2) Run experiment with returned `scenario_id`:

```bash
curl -sS -X POST "http://127.0.0.1:8000/experiments/run" \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"<SCENARIO_ID>","config":{"repeats":1,"classical_solver":"cp_sat","hybrid_solver":"qubo_hybrid","run_mode":"parallel","seed_policy":"fixed","benchmark_preset":"custom","density_clamp_mode":"off","common_budget":{"max_time_seconds":3.0,"max_iterations":30,"seed":111,"strict_parity_mode":true}}}'
```

3) Export:

```bash
curl -sS "http://127.0.0.1:8000/experiments/<EXPERIMENT_ID>/export?format=json"
curl -sS "http://127.0.0.1:8000/experiments/<EXPERIMENT_ID>/export?format=csv"
```

## How To Run Small Experiments

Use the same pattern as toy, but:
- `preset: "small"`
- explicit safety config (e.g., `benchmark_preset: "custom"`, `density_clamp_mode: "off"`)
- strict parity and any diagnostic overrides (`sector_balanced_candidates`, cap/stride overrides) must be explicit in `common_budget`.

## Fairness Labels (Quick Reference)

- `exploratory-only`: strict parity off
- `strong-approximate-comparable`: strict parity on, hybrid present, no repair-assisted markers
- `repair-assisted approximate-comparable`: strict parity on + repair-assisted hybrid decode markers
- `exact-comparable`: **not used** in this repository for CP-SAT vs QUBO-hybrid comparisons

## Certification / Geometry Validity Flags

- `placement_geometry_valid`: whether the reported placement can be interpreted geometrically
- `solver_certified_geometry` (CSV export): conservative boolean requiring geometry validity and no extraction-invalid marker
- CP-SAT infeasible/non-certified runs intentionally return empty placements with invalid geometry flags to prevent false interpretation

## Density Achievability Metadata

Per experiment, `density_achievability` includes:
- `achievable_density_min` / `achievable_density_max`
- `achievability_degenerate`
- `target_inside_achievable_band`
- `benchmark_comparable` / `benchmark_non_comparable`
- requested vs stored target fields and clamp-applied status

## Explicit Fallback vs Default Benchmark Mode

- Default benchmark mode: `density_clamp_mode="off"` (no silent target modification)
- Explicit fallback mode: `density_clamp_mode="explicit_fallback"` (target may be adjusted into valid band, and run must be interpreted accordingly)

## Evidence / Artifacts Guide

Artifacts are saved under `evidence/` and typically include:
- `request_meta.json`: exact payload used
- `run_summary.json`: experiment/scenario IDs
- `export.json`: full experiment + stats + metadata
- `export.csv`: trial-level compact view

Recent diagnostic directories include:
- `small_feasibility_diagnosis/`
- `small_sector_balance_recheck_seed123/`
- `small_cap_increase_audit_seed123/`
- `small_stride_xy_counterfactual_seed123/`

## Known Limitations

- CP-SAT uses hard constraints; QUBO uses penalty-encoded constraints + decode heuristics.
- Hybrid fallback runtime can exceed intuitive budget expectations.
- Candidate discretization/capping strongly affects feasibility surface.
- `small` currently behaves mostly as a hard/diagnostic regime under present formulation.

## Recommended Next Steps

See:
- `docs/glossary.md` for term definitions,
- `docs/current_findings.md` for evidence-grounded status,
- `docs/methodology.md` for interpretation rules,
- `docs/reproducibility.md` for safe run protocol,
- `docs/milestones.md` for development history.
