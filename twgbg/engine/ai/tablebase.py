"""Tiny retrograde tablebase for miniature positions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from ..game import JumpWindow, Move, Position, RuleConfig, legal_responses, spoiler_legal_moves, step
from ..graphs import DiGraph
from .symmetry import canonical_position_key


@dataclass
class Tablebase:
    max_vertices: int = 6
    cache: Dict[Tuple, Optional[float]] = field(default_factory=dict)

    def probe(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        config: RuleConfig,
        *,
        round_number: int = 0,
    ) -> Optional[float]:
        if len(graph_a) + len(graph_b) > self.max_vertices:
            return None
        key = (canonical_position_key(pos, graph_a, graph_b), config.key(), round_number)
        if key not in self.cache:
            self.cache[key] = self._solve(graph_a, graph_b, pos, config, round_number, JumpWindow(limit=config.jump_cooldown))
        return self.cache[key]

    def _solve(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        config: RuleConfig,
        round_number: int,
        jump_window: JumpWindow,
    ) -> Optional[float]:
        if config.round_limit is not None and round_number >= config.round_limit:
            return -float("inf")
        moves = spoiler_legal_moves(graph_a, graph_b, pos, config, jump_window, round_number)
        if not moves:
            return -float("inf")
        result = -float("inf")
        for move in moves:
            target_graph = graph_b if move.side == "A" else graph_a
            replies = legal_responses(target_graph, pos, move, config)
            if not replies:
                return float("inf")
            all_survive = True
            for reply in replies:
                jw = JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
                new_pos, alive, info = step(
                    graph_a,
                    graph_b,
                    pos,
                    move,
                    reply,
                    config=config,
                    jump_window=jw,
                    round_number=round_number,
                )
                if "Spoiler wins" in info:
                    return float("inf")
                if not alive:
                    # Duplicator wins because round limit reached
                    continue
                sub = self._solve(graph_a, graph_b, new_pos, config, round_number + 1, jw)
                if sub == float("inf"):
                    all_survive = False
                    break
            if all_survive:
                result = max(result, -float("inf"))
        return result


__all__ = ["Tablebase"]
