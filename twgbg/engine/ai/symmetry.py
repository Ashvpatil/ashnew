"""Canonicalisation helpers used by search engines."""
from __future__ import annotations

from typing import Dict, Tuple

from ..game import Position
from ..graphs import DiGraph


def _canonical_graph_signature(graph: DiGraph) -> Tuple[Tuple[int, Tuple[int, ...]], ...]:
    vertices = graph.vertices()
    index = {v: i for i, v in enumerate(vertices)}
    signature = []
    for v in vertices:
        succ = tuple(sorted(index[w] for w in graph.successors(v)))
        pred = tuple(sorted(index[w] for w in graph.predecessors(v)))
        signature.append((index[v], succ + (-1,) + pred))
    signature.sort()
    return tuple(signature)


def canonical_position_key(pos: Position, graph_a: DiGraph, graph_b: DiGraph) -> Tuple:
    sig_a = _canonical_graph_signature(graph_a)
    sig_b = _canonical_graph_signature(graph_b)
    idx_a = {v: i for i, v in enumerate(graph_a.vertices())}
    idx_b = {v: i for i, v in enumerate(graph_b.vertices())}
    return (sig_a, sig_b, idx_a.get(pos.A_curr, -1), idx_b.get(pos.B_curr, -1))


__all__ = ["canonical_position_key"]
