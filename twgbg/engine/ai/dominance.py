"""Dominance heuristics for pruning weak Spoiler moves."""
from __future__ import annotations

from typing import Iterable, List

from ..game import Move, Position, RuleConfig, legal_responses
from ..graphs import DiGraph


def filter_dominated(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    moves: Iterable[Move],
    config: RuleConfig,
) -> List[Move]:
    """Filter out moves that are clearly inferior by reply-count dominance.

    The heuristic groups moves by (side, move type) and keeps only those whose
    number of legal replies is within one of the minimal value.  This retains a
    diverse set of tactical options while trimming the search tree.
    """

    groups = {}
    for move in moves:
        key = (move.side, move.mtype)
        graph = graph_b if move.side == "A" else graph_a
        replies = legal_responses(graph, pos, move, config)
        count = len(replies)
        entry = groups.setdefault(key, [])
        entry.append((count, move))
    filtered: List[Move] = []
    for key, items in groups.items():
        items.sort(key=lambda x: x[0])
        if not items:
            continue
        min_count = items[0][0]
        threshold = min_count + 1
        filtered.extend(mv for count, mv in items if count <= threshold)
    return filtered


__all__ = ["filter_dominated"]
