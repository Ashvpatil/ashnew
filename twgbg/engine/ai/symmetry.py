"""Simple canonical labelling to prune symmetric positions."""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

from ..graphs import DiGraph


def _sorted_adjacency(graph: DiGraph) -> Tuple[str, ...]:
    items = []
    for v in sorted(graph.succ):
        succs = ",".join(sorted(graph.succ[v]))
        preds = ",".join(sorted(graph.pred[v]))
        items.append(f"{v}:{succs}|{preds}")
    return tuple(items)


def canonical_label(graph_a: DiGraph, graph_b: DiGraph, a_curr: str | None, b_curr: str | None) -> str:
    """Return a canonical string representing the position."""

    summary = [
        "SYM",
        ";".join(_sorted_adjacency(graph_a)),
        ";".join(_sorted_adjacency(graph_b)),
        a_curr or "_",
        b_curr or "_",
    ]
    return "|".join(summary)
