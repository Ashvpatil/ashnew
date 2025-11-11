"""Utility helpers shared across engine modules."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


class RNG:
    """Deterministic RNG wrapper used for reproducible experiments."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._random = random.Random(seed)

    def choice(self, seq: Sequence[Any]) -> Any:
        if not seq:
            raise ValueError("Cannot choose from empty sequence")
        return seq[self._random.randrange(len(seq))]

    def weighted_choice(self, items: Sequence[Tuple[Any, float]]) -> Any:
        total = sum(weight for _, weight in items)
        if total <= 0:
            return self.choice([item for item, _ in items])
        r = self._random.random() * total
        upto = 0.0
        for item, weight in items:
            upto += weight
            if r <= upto:
                return item
        return items[-1][0]

    def shuffle(self, seq: list) -> None:
        self._random.shuffle(seq)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def random(self) -> float:
        return self._random.random()


@dataclass
class Timer:
    """Simple performance timer returning millisecond resolution."""

    start: float = time.perf_counter()

    def reset(self) -> None:
        self.start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.start) * 1000.0


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf8") as fh:
        return json.load(fh)


def save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)


def format_duration(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms/1000:.2f} s"


__all__ = ["RNG", "Timer", "ensure_dir", "load_json", "save_json", "format_duration"]
