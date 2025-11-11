"""Graph bisimulation signatures for analysis tab."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from ..engine.graphs import DiGraph


def signature_partition(graph: DiGraph) -> Dict[str, Tuple[int, Tuple[int, ...], Tuple[int, ...]]]:
    partition: Dict[str, Tuple[int, Tuple[int, ...], Tuple[int, ...]]] = {}
    vertices = graph.vertices()
    for v in vertices:
        succ_multiset = tuple(sorted(len(graph.successors(w)) for w in graph.successors(v)))
        pred_multiset = tuple(sorted(len(graph.predecessors(w)) for w in graph.predecessors(v)))
        partition[v] = (len(graph.successors(v)), succ_multiset, pred_multiset)
    return partition


__all__ = ["signature_partition"]
