"""Light-weight table-based evaluation support."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple
import json
import os

from ..engine.game import Position, Move


@dataclass
class TabularValue:
    """Stores approximate state values learnt from self-play."""

    values: Dict[Tuple, float] = field(default_factory=dict)
    alpha: float = 0.3

    def get(self, position: Position) -> float:
        return self.values.get(position.as_tuple(), 0.0)

    def update(self, trajectory: Iterable[Tuple[Position, float]]) -> None:
        for position, target in trajectory:
            key = position.as_tuple()
            current = self.values.get(key, 0.0)
            self.values[key] = current + self.alpha * (target - current)

    def save(self, path: str) -> None:
        payload = {repr(k): v for k, v in self.values.items()}
        with open(path, "w", encoding="utf8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf8") as fh:
            raw = json.load(fh)
        self.values = {eval(k): float(v) for k, v in raw.items()}


def self_play_update(value_fn: TabularValue, logs: Iterable[Tuple[Move, float]]) -> None:
    """Very small helper for running learning experiments.

    The GUI hooks expose this helper to allow capturing move/value pairs during
    analysis runs.  The update rule is intentionally tiny to keep unit tests
    fast; it simply nudges the stored value towards the empirical target.
    """

    for move, outcome in logs:
        # As an example we only key on the move's source/target ignoring the
        # graphs.  More advanced projects can swap in neural heuristics.
        key = (move.graph, move.source, move.target)
        current = value_fn.values.get(key, 0.0)
        value_fn.values[key] = current + value_fn.alpha * (outcome - current)
