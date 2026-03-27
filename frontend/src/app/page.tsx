"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE, api } from "@/lib/api";
import type { ExperimentConfig, GenerateScenarioRequest, InstanceFeatures, Scenario } from "@/types/api";

type Trial = {
  trial_index: number;
  solver_kind: "classical" | "hybrid";
  solver_name: string;
  backend_type: string;
  elapsed_ms: number;
  objective: number;
  feasible: boolean;
  violation_breakdown: Record<string, number>;
  solution?: {
    placements: Array<{
      block_id: string;
      sector_id: string;
      orientation: 0 | 1;
      x: number;
      y: number;
      z: number;
      height: number;
    }>;
    violations: string[];
    placement_geometry_valid: boolean;
    solver_metadata?: Record<string, unknown>;
  };
};

type ResultsPayload = {
  experiment: {
    id: string;
    scenario: Scenario & { density_target: number };
    config: ExperimentConfig;
    density_achievability?: Record<string, unknown>;
    trials: Trial[];
  };
  stats: {
    fairness_report?: {
      comparison_type?: string;
      interpretation_guidance?: string;
    };
  };
  instance_features?: InstanceFeatures;
};

const defaultScenario: GenerateScenarioRequest = {
  preset: "toy",
  seed: 111,
  density_target: 0.55,
  compatibility_strength: 1,
  objective_weights: {
    active_sectors: 1,
    skyline_height: 1,
    compactness: 1,
    density_deviation: 1,
    compatibility: 1,
    accessibility: 0.5
  }
};

const defaultConfig: ExperimentConfig = {
  repeats: 1,
  classical_solver: "cp_sat",
  hybrid_solver: "qubo_hybrid",
  run_mode: "parallel",
  seed_policy: "fixed",
  benchmark_preset: "custom",
  fairness_classification: "repair-assisted approximate-comparable",
  density_clamp_mode: "off",
  penalty_sweep: { enabled: false, candidates: [5, 10, 20, 30], selection_metric: "feasibility_then_objective" },
  common_budget: {
    max_time_seconds: 3,
    max_iterations: 30,
    seed: 111,
    warm_start: false,
    penalty_scale: 60,
    strict_parity_mode: true,
    sector_balanced_candidates: true
  }
};

const toySeeds = [
  { label: "Seed 111", value: 111, note: "baseline toy preset seed" },
  { label: "Seed 222", value: 222, note: "alternate toy preset seed" },
  { label: "Seed 333", value: 333, note: "alternate toy preset seed" }
];

function formatMs(ms?: number) {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms.toFixed(1)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function certifiedGeometry(trial?: Trial): boolean {
  if (!trial?.solution) return false;
  const meta = trial.solution.solver_metadata ?? {};
  return Boolean(trial.solution.placement_geometry_valid && !meta.placement_extraction_invalid);
}

function fmtNum(x: unknown, digits = 4) {
  if (x == null) return "unavailable";
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "unavailable";
  return n.toFixed(digits);
}

function fmtInt(x: unknown) {
  if (x == null) return "unavailable";
  const n = typeof x === "number" ? x : Number(x);
  if (!Number.isFinite(n)) return "unavailable";
  return String(Math.trunc(n));
}

function PlacementView({
  trial,
  scenario,
  running = false,
  activityLabel = "Preparing"
}: {
  trial?: Trial;
  scenario?: Scenario | null;
  running?: boolean;
  activityLabel?: string;
}) {
  if (running && !trial?.solution) {
    return (
      <div className="space-y-3">
        <div className="text-xs text-slate-400">In progress: {activityLabel}</div>
        <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
          <div className="grid grid-cols-6 gap-1 opacity-70">
            {Array.from({ length: 24 }).map((_, i) => (
              <div
                key={i}
                className="h-6 rounded bg-slate-800/70 animate-pulse"
                style={{ animationDelay: `${(i % 6) * 80}ms` }}
              />
            ))}
          </div>
        </div>
        <div className="text-xs text-slate-500">
          Activity view only. This does not show optimization convergence.
        </div>
      </div>
    );
  }

  if (!scenario) {
    return (
      <div className="flex h-full min-h-[260px] items-center justify-center rounded-md border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
        No scenario loaded yet.
      </div>
    );
  }

  if (!trial?.solution) {
    return (
      <div className="flex h-full min-h-[260px] items-center justify-center rounded-md border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
        Run the benchmark to populate placements.
      </div>
    );
  }
  const placements = trial.solution.placements ?? [];
  if (!placements.length) {
    return (
      <div className="flex h-full min-h-[260px] flex-col items-center justify-center rounded-md border border-slate-800 bg-slate-950/40 p-4 text-sm">
        <div className="font-medium text-slate-200">No certified placement extracted.</div>
        <div className="mt-1 text-xs text-slate-400 max-w-md text-center">
          This usually means the solver did not certify a feasible layout for this case, so no geometry is shown.
          If geometry is not certified/valid, placements should not be interpreted as a physical layout.
        </div>
      </div>
    );
  }

  const sectorMap = new Map(scenario.sectors.map((s) => [s.id, s]));
  const blockMap = new Map(scenario.blocks.map((b) => [b.id, b]));
  const firstSector = placements[0]?.sector_id;
  const sec = sectorMap.get(firstSector);
  if (!sec) return <div className="text-sm text-slate-400">Unknown sector in placements.</div>;

  const scale = 10;
  const width = sec.width * scale;
  const height = sec.depth * scale;

  const rects = placements.map((p) => {
    const b = blockMap.get(p.block_id);
    if (!b) return null;
    const w = p.orientation === 1 ? b.depth : b.width;
    const d = p.orientation === 1 ? b.width : b.depth;
    return {
      id: p.block_id,
      x: p.x * scale,
      y: p.y * scale,
      w: w * scale,
      h: d * scale
    };
  }).filter(Boolean) as Array<{ id: string; x: number; y: number; w: number; h: number }>;

  const overlapSet = new Set<string>();
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i];
      const b = rects[j];
      const overlap = !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
      if (overlap) {
        overlapSet.add(a.id);
        overlapSet.add(b.id);
      }
    }
  }

  return (
    <div className="space-y-2">
      <div className="text-xs text-slate-400">
        Sector `{firstSector}` top-down view. Red blocks indicate overlap in XY projection.
      </div>
      <div className="rounded-md border border-slate-800 bg-slate-950/60 p-2">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-[360px] w-full rounded bg-slate-950"
          preserveAspectRatio="xMidYMid meet"
        >
          <rect x={0} y={0} width={width} height={height} fill="transparent" stroke="#334155" />
        {rects.map((r) => (
          <g key={r.id}>
            <rect
              x={r.x}
              y={r.y}
              width={r.w}
              height={r.h}
              fill={overlapSet.has(r.id) ? "#ef4444" : "#38bdf8"}
              opacity={overlapSet.has(r.id) ? 0.55 : 0.35}
              stroke={overlapSet.has(r.id) ? "#fecaca" : "#bae6fd"}
              strokeWidth={1.5}
            />
            <text x={r.x + 4} y={r.y + 14} fontSize={11} fill="#e2e8f0">
              {r.id}
            </text>
          </g>
        ))}
        </svg>
      </div>
    </div>
  );
}

function KeyMetric({
  label,
  value,
  mono = false,
  help,
}: {
  label: string;
  value: string;
  mono?: boolean;
  help?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-800/60 py-2 last:border-b-0">
      <div className="text-xs uppercase tracking-wide text-slate-400">
        <span className="whitespace-nowrap" title={help}>{label}</span>
        {help ? <span className="ml-2 text-[11px] normal-case tracking-normal text-slate-500">({help})</span> : null}
      </div>
      <div className={mono ? "font-mono text-sm text-slate-100" : "text-sm text-slate-100"}>{value}</div>
    </div>
  );
}

export default function HomePage() {
  const [scenarioReq, setScenarioReq] = useState(defaultScenario);
  const [cfg, setCfg] = useState(defaultConfig);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [expId, setExpId] = useState<string>("");
  const [results, setResults] = useState<ResultsPayload | null>(null);
  const [status, setStatus] = useState("idle");
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const trialRows = useMemo(() => results?.experiment?.trials ?? [], [results]);
  const classical = trialRows.find((t) => t.solver_kind === "classical");
  const hybrid = trialRows.find((t) => t.solver_kind === "hybrid");
  const densityMeta = (results?.experiment?.density_achievability ?? {}) as Record<string, unknown>;
  const fairness = results?.stats?.fairness_report?.comparison_type ?? results?.experiment?.config?.fairness_classification ?? "-";
  const instance = results?.instance_features;

  const comparable = Boolean(densityMeta.benchmark_comparable);
  const nonComparable = Boolean(densityMeta.benchmark_non_comparable);
  const readiness: "benchmark-comparable" | "diagnostic-only" | "non-comparable" =
    nonComparable ? "non-comparable" : comparable ? "benchmark-comparable" : "diagnostic-only";
  const readinessTone =
    readiness === "benchmark-comparable"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
      : readiness === "non-comparable"
        ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
        : "border-amber-500/40 bg-amber-500/10 text-amber-200";

  useEffect(() => {
    if (status !== "running" || runStartedAt == null) return;
    const id = window.setInterval(() => setElapsedMs(Date.now() - runStartedAt), 250);
    return () => window.clearInterval(id);
  }, [status, runStartedAt]);

  const run = async () => {
    setStatus("running");
    setRunStartedAt(Date.now());
    setElapsedMs(0);
    try {
      const sc = (await api.generateScenario({ ...scenarioReq, preset: "toy" })) as Scenario;
      setScenario(sc);
      const cfgRun: ExperimentConfig = {
        ...cfg,
        repeats: 1,
        benchmark_preset: "custom",
        seed_policy: "fixed",
        density_clamp_mode: "off",
        fairness_classification: "repair-assisted approximate-comparable",
        penalty_sweep: { ...cfg.penalty_sweep, enabled: false },
        common_budget: {
          ...cfg.common_budget,
          seed: scenarioReq.seed,
          strict_parity_mode: cfg.common_budget.strict_parity_mode,
          sector_balanced_candidates: true
        }
      };
      const exp = await api.runExperiment(sc.id, cfgRun);
      setExpId(exp.experiment_id);
      const r = (await api.getResults(exp.experiment_id)) as ResultsPayload;
      setResults(r);
      setStatus("completed");
      setRunStartedAt(null);
    } catch (e) {
      setStatus(`failed: ${(e as Error).message}`);
      setRunStartedAt(null);
    }
  };

  const exportData = async (format: "json" | "csv") => {
    if (!expId) return;
    const data = await api.exportResults(expId, format);
    const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = `experiment_${expId}.${format}`;
    a.click();
    URL.revokeObjectURL(href);
  };

  const reset = () => {
    setScenarioReq(defaultScenario);
    setCfg(defaultConfig);
    setScenario(null);
    setExpId("");
    setResults(null);
    setStatus("idle");
    setRunStartedAt(null);
    setElapsedMs(0);
  };

  const diagnosticOnly = Boolean(densityMeta.benchmark_non_comparable) || fairness === "exploratory-only";
  const interpretation = [
    densityMeta.benchmark_comparable
      ? "This toy run is benchmark-comparable for density."
      : "This run should be treated as diagnostic (non-comparable density conditions).",
    classical?.solution?.placement_geometry_valid
      ? "Classical solver returned geometrically valid placements."
      : "Classical solver did not return certified geometry.",
    hybrid?.feasible
      ? "Hybrid solver returned a feasible decoded placement."
      : "Hybrid solver returned a decoded but infeasible placement.",
    `Interpret as ${fairness}; this is not exact solver parity.`
  ];

  const semanticClassical = classical?.solution?.violations ?? [];
  const semanticHybrid = hybrid?.solution?.violations ?? [];
  const semanticCountClassical = semanticClassical.length;
  const semanticCountHybrid = semanticHybrid.length;

  const clampApplied = Boolean(densityMeta.density_clamp_applied);
  const storedDensity = densityMeta.density_target_stored_for_solve ?? "unavailable";

  const hasResults = Boolean(results?.experiment?.id);
  const expScenario = results?.experiment?.scenario ?? scenario;

  const readinessHelp =
    "Comparable means density conditions are structurally aligned for inspection; diagnostic/non-comparable runs should not be treated as benchmark evidence.";
  const fairnessHelp =
    "A label describing how directly the two methods can be compared (often approximate, sometimes repair-assisted).";
  const repairAssistedHelp =
    "Hybrid decode/repair was used to turn an approximate sample into a placement to evaluate; not exact parity with CP-SAT.";
  const certifiedHelp =
    "Better if true. Certified geometry means the placement is safe to interpret as a real layout (not just a decoded proposal).";
  const geomValidHelp =
    "Better if true. Placement geometry valid indicates the solver produced placements that pass basic geometry/consistency checks.";
  const feasibleHelp = "Better if true. False means the solver did not satisfy all constraints for this run.";
  const runtimeHelp = "Lower is usually better, but only compare after checking readiness and certification.";
  const objectiveHelp =
    "Lower is usually better within the same comparable run, but only meaningful when a certified valid layout exists.";
  const overlapHelp = "Lower is better; 0 is best (no overlaps). Only meaningful for certified valid layouts.";
  const densityViolationHelp =
    "Lower is better; 0 is best (meets density target/constraints). Only meaningful for certified valid layouts.";

  const classicalCertified = certifiedGeometry(classical);
  const hybridCertified = certifiedGeometry(hybrid);
  const classicalFeasible = classical?.feasible;
  const hybridFeasible = hybrid?.feasible;

  const evaluatedLayout = (t?: Trial) => Boolean(t && certifiedGeometry(t));
  const metricOrDash = (t: Trial | undefined, compute: () => string) =>
    evaluatedLayout(t) ? compute() : "—";

  const overlapCount = (t?: Trial) => t?.violation_breakdown?.overlap_violations;
  const densityCount = (t?: Trial) => t?.violation_breakdown?.density_violations;

  const constraintStatus = (t?: Trial) => {
    const certified = evaluatedLayout(t);
    const overlapOk = certified && (overlapCount(t) ?? 0) === 0;
    const densityOk = certified && (densityCount(t) ?? 0) === 0;
    return {
      certified_assignment: certified,
      no_overlap: overlapOk,
      density_target: densityOk,
    };
  };

  const ConditionPill = ({ ok, label }: { ok: boolean; label: string }) => (
    <span
      className={
        ok
          ? "inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-200"
          : "inline-flex items-center rounded-full border border-slate-700 bg-slate-950/40 px-2 py-0.5 text-[11px] text-slate-300"
      }
      title={ok ? "satisfied" : "not satisfied / not evaluated"}
    >
      {label}: {ok ? "satisfied" : "not satisfied"}
    </span>
  );

  const solverStatusLine = (kind: "classical" | "hybrid") => {
    const t = kind === "classical" ? classical : hybrid;
    const name = kind === "classical" ? "classical" : "hybrid";
    if (!hasResults || !t) return `No ${name} result yet. Run the benchmark to populate outcomes.`;
    const feasible = t.feasible;
    const certified = certifiedGeometry(t);
    const geomValid = t.solution?.placement_geometry_valid;

    if (!feasible && kind === "classical") {
      return "The classical solver did not certify a feasible valid layout for this run, so no geometry is shown.";
    }
    if (!feasible && kind === "hybrid") {
      return "The hybrid solver returned a decoded layout proposal, but it is still infeasible (violations remain).";
    }
    if (feasible && !certified) {
      return "A solution record exists, but it is not certified as valid geometry—interpret placements cautiously.";
    }
    if (feasible && certified && geomValid === false) {
      return "The solver reports feasibility, but geometry validity is false—do not interpret this as a successful layout.";
    }
    if (feasible && certified) {
      return "A feasible solution with certified geometry is available for interpretation.";
    }
    return "Results are present, but certification/validity is unclear—treat as diagnostic.";
  };

  const nonExpertSummary = useMemo(() => {
    if (!hasResults) return [];
    const lines: string[] = [];
    if (readiness === "benchmark-comparable") {
      lines.push("This toy case is benchmark-comparable, so the two methods can be inspected side by side.");
    } else if (readiness === "non-comparable") {
      lines.push("This toy case is non-comparable, so it should be treated as diagnostic-only.");
    } else {
      lines.push("This toy case is diagnostic-only (not clean benchmark evidence).");
    }

    if (classicalFeasible === false || classicalCertified === false) {
      lines.push("The classical solver did not return a certified feasible layout in this run.");
    } else if (classicalCertified) {
      lines.push("The classical solver returned a certified feasible layout in this run.");
    }

    if (hybridFeasible === false || hybridCertified === false) {
      lines.push("The hybrid solver produced a layout proposal, but it still contains rule violations or lacks certification.");
    } else if (hybridCertified) {
      lines.push("The hybrid solver returned a feasible decoded layout with certified geometry in this run.");
    }

    lines.push("This dashboard does not show quantum advantage. It shows how two methods behave on the same toy case.");
    return lines;
  }, [hasResults, readiness, classicalFeasible, hybridFeasible, classicalCertified, hybridCertified]);

  const runIsActive = status === "running";
  const stageFromElapsed = (solver: "classical" | "hybrid") => {
    const t = elapsedMs / 1000;
    // Honest lifecycle estimate from frontend run flow (not backend convergence telemetry).
    if (t < 1.2) return "Preparing scenario";
    if (t < 2.4) return "Building candidate graph";
    if (solver === "classical") {
      if (t < 3.8) return "Building optimization model";
      if (t < 7.5) return "Solving";
      if (t < 9.0) return "Evaluating";
      return "Finalizing";
    }
    if (t < 3.8) return "Building QUBO";
    if (t < 10.0) return "Sampling";
    if (t < 12.5) return "Decoding";
    if (t < 14.0) return "Evaluating";
    return "Finalizing";
  };
  const solverLiveState = (solver: "classical" | "hybrid") => {
    const t = solver === "classical" ? classical : hybrid;
    const stage = stageFromElapsed(solver);
    return {
      stage,
      elapsed: formatMs(elapsedMs),
      decodedAvailable: Boolean(t?.solution),
      evaluationComplete: Boolean(t?.solution),
    };
  };

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
      <header className="panel space-y-3">
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight">Toy Benchmark Demo</h1>
            <p className="max-w-3xl text-sm leading-relaxed text-slate-300">
              Toy-only research dashboard for CP-SAT vs hybrid-QUBO comparisons with benchmark readiness, fairness, certification, and instance hardness metadata.
            </p>
          </div>
          <div className="text-[11px] text-slate-500 md:text-right">
            API base <span className="font-mono text-slate-400">{API_BASE}</span>
          </div>
        </div>
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-200">
          Toy-only research demo. Approximate comparisons (not exact parity). No quantum-advantage claim. Read readiness + certification before interpreting outcomes.
        </div>
      </header>

      <section className="panel">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="grid w-full grid-cols-1 gap-3 md:grid-cols-4">
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-slate-400">Mode</div>
              <div className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-200">
                toy (fixed)
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-slate-400">Toy seed</div>
              <select
                className="w-full rounded-md border border-slate-800 bg-white px-3 py-2 text-sm text-black"
                value={scenarioReq.seed}
                onChange={(e) => {
                  const seed = Number(e.target.value);
                  setScenarioReq({ ...scenarioReq, seed });
                  setCfg({ ...cfg, common_budget: { ...cfg.common_budget, seed } });
                }}
              >
                {toySeeds.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label} - {s.note}
                  </option>
                ))}
              </select>
              <div className="text-[11px] leading-snug text-slate-500">
                Chooses one predefined toy benchmark case. Different seeds can be easier or harder.
              </div>
              <div className="text-[11px] leading-snug text-slate-500">
                Note: current live runs use the latest candidate-generation and hygiene rules, so an older “easy seed” may not reproduce older outcomes exactly.
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-slate-400">Density target</div>
              <input
                className="w-full rounded-md border border-slate-800 bg-white px-3 py-2 text-sm text-black"
                type="number"
                step="0.01"
                value={scenarioReq.density_target}
                onChange={(e) => setScenarioReq({ ...scenarioReq, density_target: Number(e.target.value) })}
              />
              <div className="text-[11px] leading-snug text-slate-500">
                Desired density level for this toy case. Lower target = looser/less dense desired layout; higher target = tighter/more dense desired layout. Outputs are evaluated against this target.
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-slate-400">Strict parity</div>
              <label className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={cfg.common_budget.strict_parity_mode}
                  onChange={(e) =>
                    setCfg({ ...cfg, common_budget: { ...cfg.common_budget, strict_parity_mode: e.target.checked } })
                  }
                />
                enabled
              </label>
              <div className="text-[11px] leading-snug text-slate-500">
                Uses a stricter shared candidate setup for both methods to make the comparison more controlled/fair, but it can also make the benchmark harder.
              </div>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap gap-2">
            <button
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              onClick={run}
              disabled={status === "running"}
            >
              {status === "running" ? "Running…" : "Run toy benchmark"}
            </button>
            <button className="rounded-md bg-slate-800 px-4 py-2 text-sm text-slate-200" onClick={reset}>
              Reset
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="text-sm text-slate-300">
            Status: <span className="font-medium text-slate-100">{status}</span>
          </div>
          <div className="text-xs text-slate-500">
            repeats=1 · benchmark_preset=custom · density_clamp_mode=off · sector-balanced candidates enabled
          </div>
        </div>
      </section>

      <section className="panel">
        <h2 className="text-lg font-semibold">How to read this demo</h2>
        <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
          <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-xs uppercase tracking-wide text-slate-400">Step 1</div>
            <div className="mt-1 text-sm text-slate-200">
              Check <span className="font-medium">benchmark readiness</span>.
            </div>
            <div className="mt-1 text-xs text-slate-400">Non-comparable/diagnostic runs are not benchmark evidence.</div>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-xs uppercase tracking-wide text-slate-400">Step 2</div>
            <div className="mt-1 text-sm text-slate-200">
              Check <span className="font-medium">certified geometry</span> for each solver.
            </div>
            <div className="mt-1 text-xs text-slate-400">No certification → do not interpret layouts as valid geometry.</div>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-xs uppercase tracking-wide text-slate-400">Step 3</div>
            <div className="mt-1 text-sm text-slate-200">
              Only then compare <span className="font-medium">runtime</span>, <span className="font-medium">overlaps</span>, and <span className="font-medium">density violations</span>.
            </div>
            <div className="mt-1 text-xs text-slate-400">No winner badge; comparisons are approximate.</div>
          </div>
        </div>
        <div className="mt-3 rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs text-slate-300">
          Common confusion: no layout does not mean the app is broken—it usually means the solver did not certify a feasible solution. A visible decoded layout can still be infeasible.
          This dashboard compares behavior on the same toy case, but comparisons remain approximate (not exact parity).
        </div>
      </section>

      {!hasResults ? (
        <section className="panel">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <h2 className="text-lg font-semibold">Ready when you are</h2>
              <p className="text-sm text-slate-300">
                Choose a toy seed and run the benchmark to populate results. The dashboard will then show benchmark readiness,
                fairness/certification flags, solver KPIs, and instance hardness metrics.
              </p>
              <div className="rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-400">
                Tip: interpret results in order—readiness → fairness/comparability → certification → KPIs → hardness.
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3">
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">Visualization</div>
                <div className="mt-2 flex h-[260px] items-center justify-center rounded-md border border-slate-800 bg-slate-950/40 text-sm text-slate-400">
                  No run yet. Placements will appear here.
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">Key outcomes</div>
                <div className="mt-2 text-sm text-slate-300">
                  After a run, you’ll see feasibility, certification, runtime, and violation counts side by side.
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <>
          <section className="panel space-y-3">
            <div className={`rounded-md border px-3 py-2 text-xs leading-relaxed ${readinessTone}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="font-semibold uppercase tracking-wide" title={readinessHelp}>
                  Benchmark readiness: {readiness}
                </div>
                <div className="text-[11px] opacity-90">
                  No winner badge. No quantum-advantage claim. Approximate comparisons only.
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-400">Fairness</div>
                <div className="mt-1 text-sm font-medium text-slate-100" title={fairnessHelp}>
                  {fairness}
                </div>
                {String(fairness).includes("repair-assisted") ? (
                  <div className="mt-1 text-[11px] text-slate-400" title={repairAssistedHelp}>
                    Helper: repair-assisted ≈ decoded/repair evaluation (not exact parity)
                  </div>
                ) : null}
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-400">Density target</div>
                <div className="mt-1 text-sm text-slate-100">
                  requested {String(densityMeta.density_target_requested ?? scenarioReq.density_target)} · stored {String(storedDensity)}
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  clamp applied: {String(clampApplied)} · inside band: {String(densityMeta.target_inside_achievable_band ?? "unavailable")}
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-400">Certification (quick)</div>
                <div className="mt-1 text-xs text-slate-300">
                  classical certified:{" "}
                  <span className="font-medium text-slate-100" title={certifiedHelp}>
                    {String(classicalCertified)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-300">
                  hybrid certified:{" "}
                  <span className="font-medium text-slate-100" title={certifiedHelp}>
                    {String(hybridCertified)}
                  </span>
                </div>
              </div>
            </div>

            {diagnosticOnly && (
              <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                Diagnostic note: this run is not clean benchmark evidence for strong comparison claims.
              </div>
            )}
          </section>

          <section className="panel">
            <h2 className="text-lg font-semibold">How to read the results (better vs worse)</h2>
            <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/40 px-4 py-3 text-sm text-slate-200">
              <ul className="list-disc space-y-1 pl-5">
                <li><span className="font-medium">Benchmark readiness</span>: must be checked first before comparing outcomes.</li>
                <li><span className="font-medium">Feasible</span>: better if true.</li>
                <li><span className="font-medium">Certified geometry</span>: better if true (safe to interpret as a layout).</li>
                <li><span className="font-medium">Overlap violations</span>: lower is better; 0 is best.</li>
                <li><span className="font-medium">Density violations</span>: lower is better; 0 is best.</li>
                <li><span className="font-medium">Runtime</span>: lower is usually better, but only after readiness + certification are satisfied.</li>
                <li><span className="font-medium">Objective</span>: lower is usually better within the same comparable run.</li>
              </ul>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              A dash (—) means the metric is not evaluated because no certified valid layout was available.
            </div>
          </section>

          {runIsActive && (
            <section className="panel space-y-3">
              <h2 className="text-lg font-semibold">Solver activity (in progress)</h2>
              <div className="text-sm text-slate-300">
                Activity states are lifecycle indicators from the live run flow. They are not objective/convergence traces.
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs text-slate-300">
                <div className="font-medium text-slate-200">Live comparison strip</div>
                <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                  {(["classical", "hybrid"] as const).map((solver) => {
                    const s = solverLiveState(solver);
                    return (
                      <div key={solver} className="rounded border border-slate-800 bg-slate-950/50 px-2 py-2">
                        <div className="text-[11px] uppercase tracking-wide text-slate-400">
                          {solver === "classical" ? "Classical" : "Hybrid"}
                        </div>
                        <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-1 text-[11px]">
                          <div className="text-slate-500">Elapsed</div>
                          <div className="text-slate-200">{s.elapsed}</div>
                          <div className="text-slate-500">Stage</div>
                          <div className="text-slate-200">{s.stage}</div>
                          <div className="text-slate-500">Decoded layout available</div>
                          <div className="text-slate-200">{s.decodedAvailable ? "yes" : "no (pending)"}</div>
                          <div className="text-slate-500">Evaluation complete</div>
                          <div className="text-slate-200">{s.evaluationComplete ? "yes" : "no (pending)"}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-slate-100">Classical activity</div>
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  </div>
                  <div className="text-sm text-slate-200">Stage: {stageFromElapsed("classical")}</div>
                  <div className="text-xs text-slate-400">Elapsed: {formatMs(elapsedMs)}</div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-slate-100">Hybrid activity</div>
                    <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 animate-pulse" />
                  </div>
                  <div className="text-sm text-slate-200">Stage: {stageFromElapsed("hybrid")}</div>
                  <div className="text-xs text-slate-400">Elapsed: {formatMs(elapsedMs)}</div>
                </div>
              </div>
            </section>
          )}

          <section className="panel space-y-3">
            <h2 className="text-lg font-semibold">What this means (plain-language)</h2>
            <div className="rounded-md border border-slate-800 bg-slate-950/40 px-4 py-3">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
                {nonExpertSummary.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          </section>

          <section className="panel space-y-3">
            <h2 className="text-lg font-semibold">Constraint status (derived from evaluated results)</h2>
            <div className="text-sm text-slate-300">
              These are derived from certification + evaluated violations (not hidden solver internals).
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                <div className="text-sm font-semibold text-slate-100">Classical</div>
                <div className="flex flex-wrap gap-2">
                  {(() => {
                    const s = constraintStatus(classical);
                    return (
                      <>
                        <ConditionPill ok={s.certified_assignment} label="Certified assignment" />
                        <ConditionPill ok={s.no_overlap} label="No-overlap" />
                        <ConditionPill ok={s.density_target} label="Density target" />
                      </>
                    );
                  })()}
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                <div className="text-sm font-semibold text-slate-100">Hybrid</div>
                <div className="flex flex-wrap gap-2">
                  {(() => {
                    const s = constraintStatus(hybrid);
                    return (
                      <>
                        <ConditionPill ok={s.certified_assignment} label="Certified assignment" />
                        <ConditionPill ok={s.no_overlap} label="No-overlap" />
                        <ConditionPill ok={s.density_target} label="Density target" />
                      </>
                    );
                  })()}
                </div>
              </div>
            </div>
          </section>

          <section className="panel space-y-4">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-lg font-semibold">Placements (visual focus)</h2>
              <div className="text-xs text-slate-500">Top-down view of placements in the first active sector.</div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-100">Classical</div>
                  <div className="text-xs text-slate-400">{classical?.solver_name ?? "-"} · {classical?.backend_type ?? "-"}</div>
                </div>
                <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
                  {solverStatusLine("classical")}
                </div>
                <div className="mt-3">
                  <PlacementView
                    trial={classical}
                    scenario={expScenario}
                    running={runIsActive}
                    activityLabel={stageFromElapsed("classical")}
                  />
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-100">Hybrid</div>
                  <div className="text-xs text-slate-400">{hybrid?.solver_name ?? "-"} · {hybrid?.backend_type ?? "-"}</div>
                </div>
                <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
                  {solverStatusLine("hybrid")}
                </div>
                <div className="mt-3">
                  <PlacementView
                    trial={hybrid}
                    scenario={expScenario}
                    running={runIsActive}
                    activityLabel={stageFromElapsed("hybrid")}
                  />
                </div>
                {!hybrid?.feasible && (
                  <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                    Hybrid placement may be decoded but infeasible; do not interpret as successful geometry.
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className="panel space-y-3">
            <h2 className="text-lg font-semibold">Key outcomes (side by side)</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4">
                <div className="text-sm font-semibold text-slate-100">Classical summary</div>
                <div className="mt-2">
                  <KeyMetric label="Feasible" value={String(classical?.feasible ?? "unavailable")} help={feasibleHelp} />
                  <KeyMetric label="Certified layout" value={String(classicalCertified)} help={certifiedHelp} />
                  <KeyMetric label="Decoded layout is valid" value={String(classical?.solution?.placement_geometry_valid ?? "unavailable")} help={geomValidHelp} />
                  <KeyMetric label="Runtime" value={formatMs(classical?.elapsed_ms)} help={runtimeHelp} />
                  <KeyMetric label="Objective" value={metricOrDash(classical, () => String(classical?.objective ?? "unavailable"))} mono help={objectiveHelp} />
                  <KeyMetric label="Overlap violations" value={metricOrDash(classical, () => String(overlapCount(classical) ?? "unavailable"))} help={overlapHelp} />
                  <KeyMetric label="Density violations" value={metricOrDash(classical, () => String(densityCount(classical) ?? "unavailable"))} help={densityViolationHelp} />
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4">
                <div className="text-sm font-semibold text-slate-100">Hybrid summary</div>
                <div className="mt-2">
                  <KeyMetric label="Feasible" value={String(hybrid?.feasible ?? "unavailable")} help={feasibleHelp} />
                  <KeyMetric label="Certified layout" value={String(hybridCertified)} help={certifiedHelp} />
                  <KeyMetric label="Decoded layout is valid" value={String(hybrid?.solution?.placement_geometry_valid ?? "unavailable")} help={geomValidHelp} />
                  <KeyMetric label="Runtime" value={formatMs(hybrid?.elapsed_ms)} help={runtimeHelp} />
                  <KeyMetric label="Objective" value={metricOrDash(hybrid, () => String(hybrid?.objective ?? "unavailable"))} mono help={objectiveHelp} />
                  <KeyMetric label="Overlap violations" value={metricOrDash(hybrid, () => String(overlapCount(hybrid) ?? "unavailable"))} help={overlapHelp} />
                  <KeyMetric label="Density violations" value={metricOrDash(hybrid, () => String(densityCount(hybrid) ?? "unavailable"))} help={densityViolationHelp} />
                </div>
              </div>
            </div>
          </section>

          <section className="panel space-y-3">
            <h2 className="text-lg font-semibold">Interpretation</h2>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
              {interpretation.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div className="text-xs text-slate-400">
              Fairness guidance: {results?.stats?.fairness_report?.interpretation_guidance ?? "unavailable"}
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              <button className="rounded-md bg-slate-800 px-3 py-2 text-sm text-slate-200" onClick={() => exportData("json")} disabled={!expId}>
                Export JSON
              </button>
              <button className="rounded-md bg-slate-800 px-3 py-2 text-sm text-slate-200" onClick={() => exportData("csv")} disabled={!expId}>
                Export CSV
              </button>
            </div>
          </section>

          <section className="panel">
            <details className="group">
              <summary className="cursor-pointer select-none list-none">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-lg font-semibold">Advanced benchmark details</div>
                  <div className="text-xs text-slate-500 group-open:hidden">show</div>
                  <div className="text-xs text-slate-500 hidden group-open:block">hide</div>
                </div>
                <div className="mt-1 text-sm text-slate-300">
                  Full KPI table, validity flags, and instance hardness metrics (scientific details).
                </div>
              </summary>

              <div className="mt-4 space-y-4">
                <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                  <div className="text-sm font-semibold text-slate-100">Benchmark validity</div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="space-y-1">
                      <KeyMetric label="fairness classification" value={fairness} help={fairnessHelp} />
                      <KeyMetric label="benchmark_comparable" value={String(densityMeta.benchmark_comparable ?? "unavailable")} help="Comparable for density; interpret solver KPIs only if comparable." />
                      <KeyMetric label="benchmark_non_comparable" value={String(densityMeta.benchmark_non_comparable ?? "unavailable")} />
                      <KeyMetric label="achievability_degenerate" value={String(densityMeta.achievability_degenerate ?? "unavailable")} />
                      <KeyMetric label="target_inside_achievable_band" value={String(densityMeta.target_inside_achievable_band ?? "unavailable")} />
                      <KeyMetric label="density_clamp_applied" value={String(clampApplied)} />
                    </div>
                    <div className="space-y-1">
                      <KeyMetric label="density_target_requested" value={String(densityMeta.density_target_requested ?? scenarioReq.density_target)} />
                      <KeyMetric label="density_target_stored_for_solve" value={String(storedDensity)} />
                      <KeyMetric label="classical placement_geometry_valid" value={String(classical?.solution?.placement_geometry_valid ?? "unavailable")} help={geomValidHelp} />
                      <KeyMetric label="classical solver_certified_geometry" value={String(classicalCertified)} help={certifiedHelp} />
                      <KeyMetric label="hybrid placement_geometry_valid" value={String(hybrid?.solution?.placement_geometry_valid ?? "unavailable")} help={geomValidHelp} />
                      <KeyMetric label="hybrid solver_certified_geometry" value={String(hybridCertified)} help={certifiedHelp} />
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                  <div className="text-sm font-semibold text-slate-100">Solver KPI comparison table</div>
                  <div className="overflow-x-auto">
                    <table className="min-w-[720px] w-full border-collapse text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-400">
                          <th className="border-b border-slate-800 py-2 pr-3">Metric</th>
                          <th className="border-b border-slate-800 py-2 pr-3">Classical</th>
                          <th className="border-b border-slate-800 py-2">Hybrid</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-200">
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Feasible</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{String(classical?.feasible ?? "unavailable")}</td>
                          <td className="border-b border-slate-900 py-2">{String(hybrid?.feasible ?? "unavailable")}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Certified layout</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{String(certifiedGeometry(classical))}</td>
                          <td className="border-b border-slate-900 py-2">{String(certifiedGeometry(hybrid))}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Decoded layout is valid</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{String(classical?.solution?.placement_geometry_valid ?? "unavailable")}</td>
                          <td className="border-b border-slate-900 py-2">{String(hybrid?.solution?.placement_geometry_valid ?? "unavailable")}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Objective</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{metricOrDash(classical, () => String(classical?.objective ?? "unavailable"))}</td>
                          <td className="border-b border-slate-900 py-2">{metricOrDash(hybrid, () => String(hybrid?.objective ?? "unavailable"))}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Runtime</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{formatMs(classical?.elapsed_ms)}</td>
                          <td className="border-b border-slate-900 py-2">{formatMs(hybrid?.elapsed_ms)}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Overlap violations</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{metricOrDash(classical, () => String(overlapCount(classical) ?? "unavailable"))}</td>
                          <td className="border-b border-slate-900 py-2">{metricOrDash(hybrid, () => String(overlapCount(hybrid) ?? "unavailable"))}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Density violations</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{metricOrDash(classical, () => String(densityCount(classical) ?? "unavailable"))}</td>
                          <td className="border-b border-slate-900 py-2">{metricOrDash(hybrid, () => String(densityCount(hybrid) ?? "unavailable"))}</td>
                        </tr>
                        <tr>
                          <td className="border-b border-slate-900 py-2 pr-3 text-slate-300">Semantic violation count</td>
                          <td className="border-b border-slate-900 py-2 pr-3">{String(semanticCountClassical)}</td>
                          <td className="border-b border-slate-900 py-2">{String(semanticCountHybrid)}</td>
                        </tr>
                        <tr>
                          <td className="py-2 pr-3 text-slate-300">Semantic violation labels</td>
                          <td className="py-2 pr-3 text-xs text-slate-300">{semanticClassical.join(", ") || "none"}</td>
                          <td className="py-2 text-xs text-slate-300">{semanticHybrid.join(", ") || "none"}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-2">
                  <div className="text-sm font-semibold text-slate-100">Instance hardness (instance_features)</div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="space-y-1">
                      <KeyMetric label="conflict_pair_count" value={fmtInt(instance?.conflict_pair_count)} />
                      <KeyMetric label="inter_block_conflict_count" value={fmtInt(instance?.inter_block_conflict_count)} />
                      <KeyMetric label="conflict_density" value={fmtNum(instance?.conflict_density, 5)} mono />
                      <KeyMetric label="inter_block_conflict_density" value={fmtNum(instance?.inter_block_conflict_density, 5)} mono />
                    </div>
                    <div className="space-y-1">
                      <KeyMetric label="occupancy_pressure_volume" value={fmtNum(instance?.occupancy_pressure_volume, 4)} mono />
                      <KeyMetric label="candidate_truncation_risk" value={String(instance?.candidate_truncation_risk ?? "unavailable")} />
                      <KeyMetric label="candidates_total" value={fmtInt(instance?.candidates_total)} />
                      <KeyMetric
                        label="grid (stride_xy/stride_z/cap)"
                        value={
                          instance?.grid
                            ? `${instance.grid.stride_xy ?? "?"} / ${instance.grid.stride_z ?? "?"} / ${instance.grid.max_candidates_per_block ?? "?"}`
                            : "unavailable"
                        }
                        mono
                      />
                    </div>
                  </div>
                </div>
              </div>
            </details>
          </section>
        </>
      )}
    </main>
  );
}
