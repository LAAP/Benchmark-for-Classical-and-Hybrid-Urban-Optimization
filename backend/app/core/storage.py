from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from app.domain.models import ExperimentRecord, Scenario

DB_PATH = Path(__file__).resolve().parents[2] / "benchmark.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scenarios (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        )
    """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


def save_scenario(scenario: Scenario) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO scenarios(id, payload) VALUES (?, ?)",
        (scenario.id, scenario.model_dump_json()),
    )
    conn.commit()
    conn.close()


def load_scenario(scenario_id: str) -> Optional[Scenario]:
    conn = get_conn()
    row = conn.execute("SELECT payload FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return Scenario.model_validate(json.loads(row["payload"]))


def save_experiment(exp: ExperimentRecord) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO experiments(id, payload) VALUES (?, ?)",
        (exp.id, exp.model_dump_json()),
    )
    conn.commit()
    conn.close()


def load_experiment(experiment_id: str) -> Optional[ExperimentRecord]:
    conn = get_conn()
    row = conn.execute("SELECT payload FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return ExperimentRecord.model_validate(json.loads(row["payload"]))
