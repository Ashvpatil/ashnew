"""Graph reducer utilities used in experiments."""
from __future__ import annotations

from typing import Callable

from ..engine.graphs import DiGraph


def reduce_graph(graph: DiGraph, predicate: Callable[[str], bool]) -> DiGraph:
    new = graph.copy()
    for v in list(graph.vertices()):
        if not predicate(v):
            new.remove_vertex(v)
    return new


__all__ = ["reduce_graph"]
