## 2-minute live demo script (toy dashboard)

Hi everyone—this is a small research benchmarking framework for discretized urban-design placement problems.

The benchmark compares two methods on the *same toy instance*: a classical baseline using OR-Tools CP-SAT, and a hybrid QUBO-style workflow (D-Wave hybrid when available, otherwise a classical fallback sampler).

This demo is **toy-only** on purpose. Toy instances let us validate benchmark hygiene—fairness labels, density achievability, certification flags, and structural diagnostics—without overclaiming from difficult regimes.

The first thing to look at is the **Benchmark readiness** banner. If it says *non-comparable* or *diagnostic-only*, we should not treat the run as benchmark evidence.

Next, check the **fairness classification** and the density metadata. This is where we make it explicit that most comparisons here are **approximate**, not exact parity.

Then we check **certification / geometry validity**. If the classical solution is not solver-certified or geometry-valid, we should not interpret any placement picture as real geometry.

After that, we can inspect the **Solver KPI table**: feasibility, objective, runtime, and any overlap or density violations. The dashboard deliberately does not declare a “winner”—these are KPIs for inspection, not a superiority claim.

We also show **instance hardness** metrics like conflict density and occupancy pressure. These are instance-level diagnostics on the shared candidate graph—they help explain *why* a toy instance may be easy or hard.

What we *can* conclude from the demo is whether the benchmark is being executed and interpreted safely: comparable vs diagnostic status, certified vs non-certified geometry, and which violations are present.

What we *cannot* conclude is any quantum advantage, or exact parity between methods. This is a methodological tool and a research demo, not a proof of superiority.

