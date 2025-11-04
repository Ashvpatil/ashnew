"""Graph analysis helpers for bisimulation diagnostics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import json

from ..engine.graphs import DiGraph


@dataclass
class PartitionSummary:
    graph: str
    blocks: Dict[str, List[str]]


def signature_partition(graph: DiGraph) -> PartitionSummary:
    partitions: Dict[str, List[str]] = {}
    for node in graph.nodes():
        succ = tuple(sorted(graph.out_neighbours(node)))
        pred = tuple(sorted(graph.in_neighbours(node)))
        key = f"s:{succ}|p:{pred}"
        partitions.setdefault(key, []).append(node)
    for nodes in partitions.values():
        nodes.sort()
    return PartitionSummary(graph="graph", blocks=partitions)


def approximate_bisimulation(graph_a: DiGraph, graph_b: DiGraph) -> Dict[str, List[Tuple[str, str]]]:
    """Return approximate node equivalence classes across graphs."""

    result: Dict[str, List[Tuple[str, str]]] = {}
    parts_a = signature_partition(graph_a).blocks
    parts_b = signature_partition(graph_b).blocks
    for sig, nodes_a in parts_a.items():
        nodes_b = parts_b.get(sig, [])
        pairs = list(zip(nodes_a, nodes_b))
        if pairs:
            result[sig] = pairs
    return result


def export_certificate(graph_a: DiGraph, graph_b: DiGraph, path: str) -> None:
    certificate = approximate_bisimulation(graph_a, graph_b)
    with open(path, "w", encoding="utf8") as fh:
        json.dump(certificate, fh, indent=2, sort_keys=True)


def reduce_counterexample(graph_a: DiGraph, graph_b: DiGraph) -> Tuple[DiGraph, DiGraph]:
    """Attempt to remove redundant nodes while preserving mismatch."""

    for graph in (graph_a, graph_b):
        removable = [
            node
            for node in list(graph.nodes())
            if not graph.out_neighbours(node) and not graph.in_neighbours(node) and len(graph) > 1
        ]
        for node in removable:
            graph.remove_node(node)
    return graph_a, graph_b
