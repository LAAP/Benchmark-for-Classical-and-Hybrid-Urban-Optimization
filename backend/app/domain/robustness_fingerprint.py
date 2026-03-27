"""
v1.6.2 toy robustness hygiene: fingerprints for deduplicating sweep rows.

Layout fingerprint (not solver outcomes):
  SHA-256 truncated to 16 hex chars of canonical JSON from structural slice of
  `compute_instance_features`: grid, sorted candidates_per_block, candidate and
  conflict counts/densities, occupancy/footprint pressure, blocks_per_sector,
  mean_block_height_span_levels.

Identical values => same discrete candidate/conflict layout for counting.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def _round_floats(obj: Any, ndigits: int = 10) -> Any:
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_round_floats(x, ndigits) for x in obj]
    return obj


def layout_fingerprint_payload_from_features(features: Dict[str, Any]) -> Dict[str, Any]:
    cpb = features.get("candidates_per_block") or {}
    sorted_cpb = dict(sorted(cpb.items())) if isinstance(cpb, dict) else cpb
    return {
        "grid": features.get("grid"),
        "candidates_per_block": sorted_cpb,
        "candidates_total": features["candidates_total"],
        "conflict_pair_count": features["conflict_pair_count"],
        "inter_block_conflict_count": features["inter_block_conflict_count"],
        "intra_block_exclusion_pairs": features["intra_block_exclusion_pairs"],
        "conflict_density": features["conflict_density"],
        "inter_block_conflict_density": features["inter_block_conflict_density"],
        "occupancy_pressure_volume": features["occupancy_pressure_volume"],
        "max_block_footprint_ratio_vs_smallest_sector": features[
            "max_block_footprint_ratio_vs_smallest_sector"
        ],
        "blocks_per_sector": features["blocks_per_sector"],
        "mean_block_height_span_levels": features["mean_block_height_span_levels"],
    }


def sweep_instance_layout_fingerprint(instance: Dict[str, Any]) -> str:
    feats = instance["features"]
    payload = _round_floats(layout_fingerprint_payload_from_features(feats))
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def fingerprint_definition_text() -> str:
    return (
        "layout_fp = sha256[:16](canonical_json(grid, sorted candidates_per_block, "
        "candidate totals, conflict counts/densities, intra_block_exclusion_pairs, "
        "occupancy/footprint pressure, blocks_per_sector, mean_block_height_span)). "
        "Solver metrics excluded."
    )
