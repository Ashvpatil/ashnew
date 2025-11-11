"""Simple tabular value store used as a soft evaluation bias."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

from ..game import Position, RuleConfig
from .symmetry import canonical_position_key


@dataclass
class LearnedBias:
    """Light-weight state value estimator trained offline via self play."""

    table: Dict[Tuple, float] = field(default_factory=dict)

    def value(self, pos: Position, graph_a=None, graph_b=None, config: RuleConfig | None = None) -> float:
        if graph_a is None or graph_b is None:
            return 0.0
        key = canonical_position_key(pos, graph_a, graph_b)
        return self.table.get(key, 0.0)

    def update(self, pos: Position, value: float, graph_a, graph_b) -> None:
        key = canonical_position_key(pos, graph_a, graph_b)
        self.table[key] = value

    def load(self, path: str) -> None:
        file = Path(path)
        if not file.exists():
            return
        data = json.loads(file.read_text(encoding="utf8"))
        self.table = {tuple(eval(k)): v for k, v in data.items()}

    def save(self, path: str) -> None:
        serialised = {repr(key): value for key, value in self.table.items()}
        Path(path).write_text(json.dumps(serialised, indent=2, sort_keys=True), encoding="utf8")


__all__ = ["LearnedBias"]
