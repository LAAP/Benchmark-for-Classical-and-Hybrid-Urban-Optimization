from __future__ import annotations

from app.core.benchmark_matrix import BENCHMARK_MATRIX


def methodology_template_for_preset(preset: str) -> dict:
    row = BENCHMARK_MATRIX.get(preset, {})
    return {
        "preset": preset,
        "standard_config": row,
        "sections": [
            "runtime summary",
            "objective summary",
            "feasibility rate",
            "per-constraint violation breakdown",
            "fairness level",
            "backend type",
            "solver mode",
            "comparison interpretability (exact/approx/exploratory)",
            "known methodological limitations",
        ],
        "limitations_prompt": [
            "State hard-vs-penalty constraint differences.",
            "State discretization and candidate truncation effects.",
            "State backend limitations (simulator fallback vs D-Wave).",
        ],
    }
