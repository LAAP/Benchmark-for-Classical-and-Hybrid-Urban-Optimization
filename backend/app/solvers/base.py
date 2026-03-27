from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import Scenario, Solution, SolverRunConfig


class SolverAdapter(ABC):
    name: str
    backend_type: str

    @abstractmethod
    def solve(self, scenario: Scenario, config: SolverRunConfig) -> tuple[Solution, list[float], list[str]]:
        raise NotImplementedError
