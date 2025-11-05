"""Utility helpers for deterministic randomness, timing and serialization."""

from __future__ import annotations

import json
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, Optional


@dataclass
class Timer:
    """Simple timer used by the engines to honour time budgets."""

    start: float

    @classmethod
    def start_new(cls) -> "Timer":
        return cls(time.perf_counter())

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.start) * 1000.0


class DeterministicRNG(random.Random):
    """Random generator with convenience helpers used throughout the project."""

    def choice_weighted(self, items: Iterable[Any], weights: Iterable[float]) -> Any:
        total = 0.0
        cumulative: list[float] = []
        items_list = list(items)
        for w in weights:
            total += max(float(w), 0.0)
            cumulative.append(total)
        if not items_list:
            raise ValueError("choice_weighted() requires at least one item")
        if total <= 0:
            return self.choice(items_list)
        r = self.random() * total
        for item, limit in zip(items_list, cumulative):
            if r <= limit:
                return item
        return items_list[-1]


def json_dump(data: Dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf8")


def json_load(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf8"))


@contextmanager
def temp_seed(seed: Optional[int]) -> Generator[None, None, None]:
    rng_state = random.getstate()
    if seed is not None:
        random.seed(seed)
    try:
        yield
    finally:
        random.setstate(rng_state)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
