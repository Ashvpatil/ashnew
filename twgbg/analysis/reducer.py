"""Heuristic reducer for counterexample graph pairs."""

from __future__ import annotations

from typing import Tuple

from ..engine.graphs import DiGraph


def trim_isolated(graph: DiGraph) -> DiGraph:
    keep = {v for v in graph.succ if graph.succ[v] or graph.pred[v]}
    if not keep:
        return graph.copy()
    new = DiGraph()
    for v in keep:
        new.add_vertex(v)
    for u in keep:
        for v in graph.succ[u]:
            if v in keep:
                new.add_edge(u, v)
    return new


def reduce_pair(graph_a: DiGraph, graph_b: DiGraph) -> Tuple[DiGraph, DiGraph]:
    return trim_isolated(graph_a), trim_isolated(graph_b)
