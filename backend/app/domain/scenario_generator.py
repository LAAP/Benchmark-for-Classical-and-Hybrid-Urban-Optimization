from __future__ import annotations

import random
from typing import Dict
from uuid import uuid4

from .models import Block, BlockType, ObjectiveWeights, Scenario, Sector


PRESETS: Dict[str, Dict[str, int]] = {
    "parity_tiny": {"blocks": 4, "sectors": 2, "sector_w": 10, "sector_d": 10, "max_h": 12},
    "toy": {"blocks": 6, "sectors": 2, "sector_w": 20, "sector_d": 20, "max_h": 25},
    "small": {"blocks": 12, "sectors": 4, "sector_w": 25, "sector_d": 25, "max_h": 35},
    "medium": {"blocks": 20, "sectors": 6, "sector_w": 30, "sector_d": 30, "max_h": 45},
    "large": {"blocks": 30, "sectors": 8, "sector_w": 35, "sector_d": 35, "max_h": 60},
}


def generate_scenario(
    *,
    seed: int,
    preset: str = "small",
    density_target: float = 0.55,
    compatibility_strength: float = 1.0,
    objective_weights: ObjectiveWeights | None = None,
) -> Scenario:
    rng = random.Random(seed)
    p = PRESETS.get(preset, PRESETS["small"])
    weights = objective_weights or ObjectiveWeights()

    sectors = [
        Sector(
            id=f"S{j}",
            width=max(10, p["sector_w"] + rng.randint(-3, 3)),
            depth=max(10, p["sector_d"] + rng.randint(-3, 3)),
            max_height=max(10, p["max_h"] + rng.randint(-5, 5)),
            capacity=100 + rng.randint(0, 150),
            context={"sun_score": rng.random(), "transit_score": rng.random()},
        )
        for j in range(p["sectors"])
    ]

    block_types = list(BlockType)
    blocks = []
    for i in range(p["blocks"]):
        btype = rng.choice(block_types)
        w = rng.randint(3, 10)
        d = rng.randint(3, 10)
        if preset == "parity_tiny":
            min_h = rng.randint(2, 4)
            max_h = min_h + rng.randint(0, 2)
        else:
            min_h = rng.randint(3, 8)
            max_h = min_h + rng.randint(1, 12)
        tags = [btype.value, "mixed_use" if rng.random() > 0.6 else "single_use"]
        blocks.append(
            Block(
                id=f"B{i}",
                width=w,
                depth=d,
                min_height=min_h,
                max_height=max_h,
                block_type=btype,
                density_weight=round(0.6 + 1.2 * rng.random(), 4),
                compatibility_tags=tags,
            )
        )

    return Scenario(
        id=f"scenario_{uuid4().hex[:10]}",
        seed=seed,
        density_target=density_target,
        compatibility_strength=compatibility_strength,
        objective_weights=weights,
        blocks=blocks,
        sectors=sectors,
    )
