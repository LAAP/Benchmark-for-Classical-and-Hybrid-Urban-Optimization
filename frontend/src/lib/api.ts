import { ExperimentConfig, GenerateScenarioRequest } from "@/types/api";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  generateScenario: (body: GenerateScenarioRequest) =>
    req("/scenarios/generate", { method: "POST", body: JSON.stringify(body) }),
  runExperiment: (scenario_id: string, config: ExperimentConfig) =>
    req<{ experiment_id: string; status: string; trial_count: number }>("/experiments/run", {
      method: "POST",
      body: JSON.stringify({ scenario_id, config })
    }),
  getResults: (id: string) => req(`/experiments/${id}/results`),
  exportResults: (id: string, format: "json" | "csv") =>
    req<{ format: string; content: string }>(`/experiments/${id}/export?format=${format}`)
};
