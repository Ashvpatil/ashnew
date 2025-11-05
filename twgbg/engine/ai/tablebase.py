"""Tiny retrograde database for very small graph pairs."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Tuple

from ..game import Move, Position, RuleConfig, legal_responses, spoiler_legal_moves
from ..graphs import DiGraph

Outcome = str  # "W", "L", "U"


@dataclass(frozen=True)
class TablebaseKey:
    a_curr: Optional[str]
    b_curr: Optional[str]
    allow_backward: bool
    allow_jump: bool


class Tablebase:
    """Retrograde solver for small positions."""

    def __init__(self) -> None:
        self.cache: Dict[Tuple[str, ...], Outcome] = {}

    def _key(self, graph_a: DiGraph, graph_b: DiGraph, pos: Position, config: RuleConfig) -> Tuple[str, ...]:
        return (
            "TB",
            pos.A_curr or "_",
            pos.B_curr or "_",
            "1" if config.allow_backward else "0",
            "1" if config.allow_jump else "0",
            str(len(graph_a.succ)),
            str(len(graph_b.succ)),
        )

    def in_scope(self, graph_a: DiGraph, graph_b: DiGraph) -> bool:
        return len(graph_a.succ) + len(graph_b.succ) <= 6

    def probe(self, graph_a: DiGraph, graph_b: DiGraph, pos: Position, config: RuleConfig) -> Outcome:
        if not self.in_scope(graph_a, graph_b):
            return "U"
        key = self._key(graph_a, graph_b, pos, config)
        if key in self.cache:
            return self.cache[key]
        outcome = self._solve(graph_a, graph_b, pos, config)
        self.cache[key] = outcome
        return outcome

    def _solve(self, graph_a: DiGraph, graph_b: DiGraph, pos: Position, config: RuleConfig) -> Outcome:
        limit = len(graph_a.succ) + len(graph_b.succ) + 2

        @lru_cache(maxsize=None)
        def rec(a_curr: Optional[str], b_curr: Optional[str], depth: int = 0) -> Outcome:
            if depth > limit:
                return "U"
            position = Position(a_curr, b_curr)
            # Try spoiler on A
            for side, graph, other_graph, current, other in (
                ("A", graph_a, graph_b, a_curr, b_curr),
                ("B", graph_b, graph_a, b_curr, a_curr),
            ):
                legal_moves = spoiler_legal_moves(
                    graph,
                    current,
                    allow_backward=config.allow_backward,
                    allow_jump=config.allow_jump,
                )
                win_found = False
                if not legal_moves:
                    continue
                for move in legal_moves:
                    move = Move(side, move.mtype, move.dest)
                    replies = legal_responses(other_graph, other, move.mtype)
                    if not replies:
                        return "W"
                    child_losses = True
                    for reply in replies:
                        if side == "A":
                            next_pos = (move.dest, reply)
                        else:
                            next_pos = (reply, move.dest)
                        res = rec(*next_pos, depth + 1)
                        if res != "L" and res != "U":
                            child_losses = False
                    if child_losses:
                        win_found = True
                if win_found:
                    return "W"
            return "L"

        return rec(pos.A_curr, pos.B_curr, 0)


def get_default_tablebase() -> Tablebase:
    return Tablebase()
