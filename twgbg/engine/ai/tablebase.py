"""Simple memoised tablebase for small positions."""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from ..game import Move, Position, RuleSet, legal_responses, spoiler_legal_moves, step
from ..graphs import DiGraph


class Tablebase:
    """A trivial tablebase storing exact results for small graphs."""

    def __init__(self) -> None:
        self.cache: Dict[Tuple[str, str], bool] = {}

    def key(self, pos: Position) -> Tuple[str, str]:
        return pos.vertex_a, pos.vertex_b

    def probe(self, pos: Position) -> Optional[bool]:
        return self.cache.get(self.key(pos))

    def record(self, pos: Position, spoiler_win: bool) -> None:
        self.cache[self.key(pos)] = spoiler_win

    def build(self, graph_a: DiGraph, graph_b: DiGraph, rules: RuleSet, max_depth: int = 4) -> None:
        """Brute-force search for tiny graphs to pre-compute results."""

        def dfs(pos: Position, depth: int) -> bool:
            cached = self.probe(pos)
            if cached is not None:
                return cached
            if depth == 0:
                self.record(pos, False)
                return False
            for move in spoiler_legal_moves(graph_a, graph_b, pos, rules):
                responses = legal_responses(graph_a, graph_b, pos, move, rules)
                if not responses:
                    self.record(pos, True)
                    return True
                spoiler_wins = True
                for reply in responses:
                    child_pos, alive, info = step(
                        graph_a, graph_b, pos, move, reply, rules
                    )
                    if not alive:
                        if not info.get("spoiler_wins"):
                            spoiler_wins = False
                            break
                        continue
                    if not dfs(child_pos, depth - 1):
                        spoiler_wins = False
                        break
                if spoiler_wins:
                    self.record(pos, True)
                    return True
            self.record(pos, False)
            return False

        for va in graph_a.vertices():
            for vb in graph_b.vertices():
                dfs(Position(va, vb), max_depth)
