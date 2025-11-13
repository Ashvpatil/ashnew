"""Bisimulation analysis utilities."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from ..engine.graphs import DiGraph


def signature_partition(graph: DiGraph) -> Dict[int, List[str]]:
    classes = defaultdict(list)
    partition = graph.partition_by_signature()
    for vertex, cls in partition.items():
        classes[cls].append(vertex)
    return dict(classes)


def approx_bisimulation_classes(graph_a: DiGraph, graph_b: DiGraph) -> Dict[str, Tuple[int, int]]:
    classes_a = graph_a.partition_by_signature()
    classes_b = graph_b.partition_by_signature()
    classes = {}
    for vertex in graph_a.vertices():
        classes["A:" + vertex] = (classes_a[vertex], -1)
    for vertex in graph_b.vertices():
        classes["B:" + vertex] = (-1, classes_b[vertex])
    return classes
