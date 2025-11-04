"""Small tablebase for positions with <= 6 vertices combined."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from ..engine.game import Move, Position


@dataclass
class Tablebase:
    """Exhaustive solver for very small graph pairs.

    The solver is deliberately conservative: it only triggers when both graphs
    are tiny which keeps unit tests cheap while still providing a noticeable
    strength boost for deterministic puzzles and late game positions.
    """

    cache: Dict[Tuple, float] = field(default_factory=dict)
    limit: int = 6

    def lookup(self, position: Position) -> Optional[float]:
        total_vertices = len(position.graph_a) + len(position.graph_b)
        if total_vertices > self.limit:
            return None
        key = position.as_tuple()
        if key in self.cache:
            return self.cache[key]
        value = self._solve(position, set())
        self.cache[key] = value
        return value

    def _solve(self, position: Position, trail: set) -> float:
        key = position.as_tuple()
        if key in trail:
            return 0.0
        trail.add(key)
        moves = position.spoiler_legal_moves()
        if not moves:
            trail.discard(key)
            return -100.0
        best = -999.0
        for move in moves:
            replies = position.legal_responses(move)
            if not replies:
                trail.discard(key)
                return 100.0
            worst = 999.0
            for reply in replies:
                child = position.clone().step(move, reply)
                child_key = child.as_tuple()
                if child_key in self.cache:
                    value = self.cache[child_key]
                elif len(child.graph_a) + len(child.graph_b) > self.limit:
                    value = 0.0
                else:
                    value = -self._solve(child, trail)
                    self.cache[child_key] = value
                worst = min(worst, value)
            best = max(best, worst)
        trail.discard(key)
        return best
