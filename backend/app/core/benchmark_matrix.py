from __future__ import annotations

from typing import Dict, List

BENCHMARK_MATRIX: Dict[str, Dict[str, object]] = {
    "parity_tiny": {"seeds": [101, 202, 303], "max_time_seconds": 2.0, "max_iterations": 25, "repeats": 3},
    "toy": {"seeds": [111, 222, 333], "max_time_seconds": 3.0, "max_iterations": 30, "repeats": 3},
    "small": {"seeds": [123, 234, 345], "max_time_seconds": 4.0, "max_iterations": 35, "repeats": 3},
}


def benchmark_seeds(preset: str) -> List[int]:
    row = BENCHMARK_MATRIX.get(preset)
    return list(row["seeds"]) if row else []
