"""Witness trace generation when Duplicator loses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import deque

from ..engine.game import Move, Position


@dataclass
class Witness:
    spoiler_moves: List[Move]
    duplicator_moves: List[Move]

    def describe(self) -> str:
        lines = ["Witness trace:"]
        for idx, (sm, dm) in enumerate(zip(self.spoiler_moves, self.duplicator_moves), start=1):
            lines.append(f"{idx}. {sm.describe()} / {dm.describe()}")
        return "\n".join(lines)


def generate_witness(position: Position, max_depth: int = 6) -> Optional[Witness]:
    """Breadth-first search for a losing sequence."""

    queue = deque([(position, [], [])])
    visited = {position.as_tuple()}
    while queue:
        state, spoiler_moves, dup_moves = queue.popleft()
        if len(spoiler_moves) >= max_depth:
            continue
        for move in state.spoiler_legal_moves():
            responses = state.legal_responses(move)
            if not responses:
                return Witness(spoiler_moves + [move], dup_moves + [Move(move.graph, move.move_type, "-", "∅")])
            for reply in responses:
                child = state.clone().step(move, reply)
                key = child.as_tuple()
                if key in visited:
                    continue
                visited.add(key)
                queue.append((child, spoiler_moves + [move], dup_moves + [reply]))
    return None
