## Toy Demo Guide (Internal)

This repository includes a **toy-only research dashboard** for demonstrating how the benchmark framework compares a **classical CP-SAT baseline** and a **hybrid QUBO-style workflow** on the same discretized toy instance, with explicit **fairness**, **comparability**, and **certification** metadata. The goal is demo clarity and safe interpretation—not product UX, not exact solver parity, and **not** a quantum-advantage claim.

> [!WARNING]
> - **Toy-only research demo** (do not generalize to `small` from this UI).
> - Comparisons are **approximate**, not exact parity.
> - This repository does **not** demonstrate quantum advantage.
> - Interpret **benchmark readiness** and **certification/geometry validity** before comparing outcomes.

### What the demo is for

- Running a **single controlled toy experiment** (one classical run + one hybrid run) and inspecting results side-by-side.
- Showing **benchmark hygiene** in practice: comparability metadata, density handling, certification flags, and structural instance metrics.
- Helping collaborators learn **how to interpret** results safely.

### What it currently supports

- Toy scenario generation (seeded).
- Single-run paired benchmark (classical vs hybrid).
- KPI comparison panels:
  - benchmark readiness + validity KPIs
  - solver KPIs (quality + efficiency)
  - instance hardness KPIs (`instance_features`)
  - plain-language interpretation block with caveats
- live solver activity section while running (lifecycle state, not convergence telemetry)
- 2D top-down placement visualization (overlap highlighting).
- JSON/CSV exports from the backend.

### What it does not support

- `small` mode in the UI (deliberately excluded).
- Benchmark sweeps or repeated campaigns from the UI.
- “Winner” badges or superiority claims.
- Exact parity claims (the hybrid path is repair-assisted/approximate-comparable in many cases).
- Any claim of quantum advantage.

### How to launch it

Backend (example on a fresh port):

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8011
```

Frontend (point to that backend):

```bash
cd frontend
NEXT_PUBLIC_API_BASE="http://localhost:8011" npm run dev -- --port 3003
```

Open:
- `http://localhost:3003`

### How to run one toy case

1) Pick a toy seed, density target, and strict parity setting.
2) Click **Run Toy Benchmark**.
3) Inspect results in the reading order below.

### How to read the dashboard (recommended order)

1) **Benchmark readiness banner**
   - `benchmark-comparable` vs `diagnostic-only` vs `non-comparable`
2) **Fairness / comparability**
   - fairness classification and density achievability metadata
3) **Certification / geometry validity**
   - `Decoded layout is valid` and `Certified layout`
4) **Solver KPIs**
   - feasible/infeasible, objective, runtime, violations, semantic flags
5) **Instance hardness**
   - `conflict_density`, `inter_block_conflict_density`, occupancy pressure, truncation risk, candidate totals
6) **Interpretation block**
   - plain-language summary with the same caveats (no advantage claims)

Also during execution:
- use the **Solver activity** section as waiting context only,
- activity stages are lifecycle labels, not optimization convergence.

### Common mistakes to avoid

- Treating a **non-comparable** or **diagnostic-only** run as benchmark evidence.
- Reading objective/runtime before checking **certification** and **geometry validity**.
- Treating a decoded hybrid placement as “successful geometry” if it is infeasible or uncertified.
- Reading `—` as “zero”: in the dashboard, `—` means **not evaluated** because no certified valid layout was available.
- Inferring any “quantum advantage” narrative from toy results.
- Generalizing toy behavior to `small` feasibility (the `small` regime is currently a hard/diagnostic regime under the present formulation).
- Assuming a seed should always reproduce old evidence exactly: current live runs use the latest candidate graph/hygiene rules, so some old toy outcomes may not match exactly.

### Where outputs go

- The backend stores experiment records and supports:
  - `GET /experiments/{id}/results` (includes `instance_features`)
  - `GET /experiments/{id}/export?format=json|csv`

