"""Dominance heuristics to prune spoiler moves."""

from __future__ import annotations

from typing import Iterable, List, Sequence

from ..game import Move


def prune_dominated(moves: Sequence[Move], reply_counts: Sequence[int]) -> List[Move]:
    """Return a filtered move list where obvious dominated moves are removed."""

    if not moves:
        return []
    best = min(reply_counts) if reply_counts else 0
    filtered: List[Move] = []
    for move, count in zip(moves, reply_counts):
        if count <= best:
            filtered.append(move)
        elif move.mtype == "jump" and count > best * 2:
            continue
        else:
            filtered.append(move)
    if not filtered:
        return list(moves)
    return filtered
