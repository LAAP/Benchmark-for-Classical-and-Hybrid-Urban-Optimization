# Reproducibility and Running Guide

Use this together with:
- `docs/methodology.md` (interpretation rules),
- `docs/current_findings.md` (current evidence status),
- `docs/glossary.md` (term definitions).

## Environment Setup

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Frontend (optional):

```bash
cd frontend
npm install
```

## Dependencies

Backend dependencies are listed in `backend/requirements.txt` (FastAPI, OR-Tools, dimod, D-Wave SDK, numpy/scipy, pytest).

## Ports Used

- Backend default: `8000`
- Frontend default: `3000`
- Common clean demo pair: backend `8011`, frontend `3000` (or `3003`+)

## Start/Restart Backend Safely

Start:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

To avoid stale-backend confusion:
- stop old server processes before restarting,
- rerun health check,
- run a tiny known request (`/scenarios/generate`) and verify response fields include expected hygiene flags in downstream exports.

## Start Frontend (and bind to intended backend)

```bash
cd frontend
NEXT_PUBLIC_API_BASE="http://localhost:8011" npm run dev -- --port 3000
```

Open `http://localhost:3000`.

The UI shows the active API base URL near the header. Use it to confirm the frontend is connected to the intended backend.

## Clean Restart Protocol (backend + frontend)

Backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8011
```

Frontend:

```bash
cd frontend
NEXT_PUBLIC_API_BASE="http://localhost:8011" npm run dev -- --port 3000
```

If either process is stale, stop old listeners first, then restart both.

## How To Run One Controlled Experiment

1) Generate scenario:

```bash
curl -sS -X POST "http://127.0.0.1:8000/scenarios/generate" \
  -H "Content-Type: application/json" \
  -d '{"preset":"small","seed":123,"density_target":0.55}'
```

2) Run experiment:

```bash
curl -sS -X POST "http://127.0.0.1:8000/experiments/run" \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"<SCENARIO_ID>","config":{"repeats":1,"classical_solver":"cp_sat","hybrid_solver":"qubo_hybrid","run_mode":"parallel","seed_policy":"fixed","benchmark_preset":"custom","density_clamp_mode":"off","common_budget":{"max_time_seconds":4.0,"max_iterations":35,"seed":123,"strict_parity_mode":true}}}'
```

3) Export:

```bash
curl -sS "http://127.0.0.1:8000/experiments/<EXPERIMENT_ID>/export?format=json"
curl -sS "http://127.0.0.1:8000/experiments/<EXPERIMENT_ID>/export?format=csv"
```

## Verify Hygiene Fixes Are Active

In export JSON, verify:
- `density_achievability.density_clamp_applied == false` (for default mode),
- `density_achievability.benchmark_comparable` and related flags are present,
- CP-SAT infeasible runs show `placement_geometry_valid=false` and `placement_extraction_invalid=true`.
- `/experiments/{id}/results` includes `instance_features` (hardness panel source).

## Output Locations

- API export endpoints return JSON/CSV payloads.
- In this repository, analysis bundles are typically saved under `evidence/<study_name>/`.

Typical files:
- `request_meta.json`
- `run_summary.json`
- `export.json`
- `export.csv`

## Inspect Export JSON/CSV

Key JSON paths:
- `experiment.config.fairness_classification`
- `experiment.density_achievability`
- `experiment.trials[*].solution.placement_geometry_valid`
- `experiment.trials[*].solution.solver_metadata`
- `stats.fairness_report`
- `instance_features` (conflict densities, truncation risk, candidate totals, grid)

Key CSV columns:
- `feasible`
- `backend_type`
- `placement_geometry_valid`
- `solver_certified_geometry`
- violation columns (`overlap_violations`, `density_violations`, etc.)

## Benchmark-Comparable vs Diagnostic

Treat a run as benchmark-comparable only if:
- `benchmark_comparable=true`,
- target is inside a non-degenerate achievable band,
- fairness label is appropriate for your claimed comparison class.

Treat as diagnostic if any of these apply:
- `benchmark_non_comparable=true`,
- explicit fallback clamp was used,
- infeasible/non-certified geometry dominates interpretation.

## Common Issues

### Frontend loads as unstyled HTML / missing Next chunk module

Symptoms:
- Tailwind/dark theme missing
- card styles missing
- errors like `Cannot find module './819.js'`

Fix:

```bash
cd frontend
rm -rf .next
npm run dev -- --port 3000
```

If still broken:

```bash
cd frontend
rm -rf .next node_modules package-lock.json
npm install
npm run dev -- --port 3000
```

### Backend mismatch (frontend points to wrong API)

- Start frontend with explicit `NEXT_PUBLIC_API_BASE`.
- Confirm the API base shown in the dashboard header.
- Verify backend health endpoint (`/health`) on that same host/port.

### Why no classical layout appears

- Usually means CP-SAT did not return a solver-certified feasible assignment for the current candidate graph.
- This is a valid diagnostic outcome, not necessarily a UI failure.

### Why a hybrid layout is visible but still infeasible

- Decoded geometry can be visible while evaluated violations remain nonzero.
- Treat this as repair-assisted approximate evidence, not a successful certified solution.
