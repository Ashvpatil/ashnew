"""Dominance filters for pruning Spoiler moves early."""
from __future__ import annotations

from typing import Dict, Iterable, List

from ..game import Move, Position, RuleSet, legal_responses
from ..graphs import DiGraph


def prune_dominated_moves(
    graph_a: DiGraph,
    graph_b: DiGraph,
    position: Position,
    moves: Iterable[Move],
    rules: RuleSet,
) -> List[Move]:
    """Filter out moves that are strictly dominated by others.

    A simple heuristic groups moves by their response signatures (the set of
    legal reply targets).  If multiple moves share an identical signature we
    keep the first one only – from Spoiler's perspective they are equivalent
    for the immediate round.
    """

    signature_map: Dict[str, Move] = {}
    filtered: List[Move] = []
    for move in moves:
        replies = legal_responses(graph_a, graph_b, position, move, rules)
        signature = "|".join(sorted(reply.target for reply in replies))
        key = f"{move.graph}:{move.move_type}:{signature}"
        if key in signature_map:
            continue
        signature_map[key] = move
        filtered.append(move)
    return filtered
