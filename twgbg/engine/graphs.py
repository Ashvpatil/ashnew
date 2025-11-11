"""Directed graph utilities for the Two-Way Global Bisimulation Game.

This module intentionally avoids third party dependencies so that the whole
project remains self contained and easy to package with PyInstaller.  The
:class:`DiGraph` class wraps two adjacency dictionaries – successors and
predecessors – and provides a tidy API for the rest of the engine and GUI.  A
number of helper routines are included for sampling graphs, serialising to JSON
and normalising labels so that downstream code never needs to worry about
integer vertices appearing in data files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import random
from typing import Dict, Iterable, Iterator, List, MutableMapping, Optional, Set, Tuple

__all__ = [
    "DiGraph",
    "normalize_labels_to_str",
    "random_digraph",
    "path_graph",
    "complete_bipartite",
    "graph_to_dict",
    "dict_to_graph",
    "load_json",
    "save_json",
]


@dataclass
class DiGraph:
    """Mutable directed graph backed by adjacency sets.

    The implementation favours clarity: all vertices are stored as strings,
    making it trivial to work with JSON data and to render labels in the GUI.
    Successors and predecessors are kept in sync whenever the graph is mutated.
    The class provides a small NetworkX-like surface area which is sufficient
    for the bisimulation game engine.
    """

    succ: Dict[str, Set[str]] = field(default_factory=dict)
    pred: Dict[str, Set[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_successors(cls, mapping: MutableMapping[str, Iterable[str]]) -> "DiGraph":
        succ: Dict[str, Set[str]] = {}
        pred: Dict[str, Set[str]] = {}
        for key, values in mapping.items():
            key_s = str(key)
            dests = {str(v) for v in values}
            succ.setdefault(key_s, set()).update(dests)
            for dest in dests:
                pred.setdefault(dest, set()).add(key_s)
        for v in list(succ):
            pred.setdefault(v, set())
        for v in list(pred):
            succ.setdefault(v, set())
        return cls(succ=succ, pred=pred)

    @classmethod
    def from_dict(cls, data: Dict[str, Iterable[str]]) -> "DiGraph":
        return cls.from_successors(data)

    def copy(self) -> "DiGraph":
        return DiGraph({k: set(v) for k, v in self.succ.items()}, {k: set(v) for k, v in self.pred.items()})

    # ------------------------------------------------------------------
    # mutation operations
    # ------------------------------------------------------------------
    def add_vertex(self, vertex: str) -> None:
        v = str(vertex)
        self.succ.setdefault(v, set())
        self.pred.setdefault(v, set())

    def remove_vertex(self, vertex: str) -> None:
        v = str(vertex)
        for src in list(self.pred.get(v, set())):
            self.succ[src].discard(v)
        for dst in list(self.succ.get(v, set())):
            self.pred[dst].discard(v)
        self.succ.pop(v, None)
        self.pred.pop(v, None)

    def add_edge(self, u: str, v: str) -> None:
        us = str(u)
        vs = str(v)
        self.add_vertex(us)
        self.add_vertex(vs)
        self.succ[us].add(vs)
        self.pred[vs].add(us)

    def remove_edge(self, u: str, v: str) -> None:
        us = str(u)
        vs = str(v)
        if us in self.succ:
            self.succ[us].discard(vs)
        if vs in self.pred:
            self.pred[vs].discard(us)

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def vertices(self) -> List[str]:
        return sorted(self.succ.keys())

    def __contains__(self, vertex: object) -> bool:
        return str(vertex) in self.succ

    def __len__(self) -> int:
        return len(self.succ)

    def successors(self, vertex: str) -> Set[str]:
        return set(self.succ.get(str(vertex), set()))

    def predecessors(self, vertex: str) -> Set[str]:
        return set(self.pred.get(str(vertex), set()))

    def out_degree(self, vertex: str) -> int:
        return len(self.succ.get(str(vertex), ()))

    def in_degree(self, vertex: str) -> int:
        return len(self.pred.get(str(vertex), ()))

    def degree(self, vertex: str) -> Tuple[int, int]:
        return (self.out_degree(vertex), self.in_degree(vertex))

    def edges(self) -> Iterator[Tuple[str, str]]:
        for u, nbrs in self.succ.items():
            for v in nbrs:
                yield (u, v)

    def ensure_closed(self) -> None:
        """Ensure both adjacency dictionaries contain all vertices."""

        for v in list(self.succ):
            self.pred.setdefault(v, set())
        for v in list(self.pred):
            self.succ.setdefault(v, set())

    def induced_subgraph(self, vertices: Iterable[str]) -> "DiGraph":
        verts = {str(v) for v in vertices}
        succ = {v: {w for w in self.succ.get(v, set()) if w in verts} for v in verts}
        return DiGraph.from_successors(succ)

    # ------------------------------------------------------------------
    # metrics
    # ------------------------------------------------------------------
    def edge_count(self) -> int:
        return sum(len(vs) for vs in self.succ.values())

    def density(self) -> float:
        n = len(self)
        if n <= 1:
            return 0.0
        return self.edge_count() / (n * (n - 1))

    # ------------------------------------------------------------------
    # serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, List[str]]:
        return {node: sorted(nbrs) for node, nbrs in self.succ.items()}


def normalize_labels_to_str(graph: DiGraph) -> DiGraph:
    mapping = {old: str(old) for old in graph.succ}
    succ: Dict[str, Set[str]] = {}
    for u, nbrs in graph.succ.items():
        nu = mapping[u]
        succ.setdefault(nu, set()).update(mapping.get(v, str(v)) for v in nbrs)
    return DiGraph.from_successors(succ)


# ----------------------------------------------------------------------
# graph generators
# ----------------------------------------------------------------------
def random_digraph(n: int, p: float, prefix: str = "N", seed: Optional[int] = None) -> DiGraph:
    if not 0 <= p <= 1:
        raise ValueError("p must be within [0, 1]")
    rng = random.Random(seed)
    succ: Dict[str, Set[str]] = {f"{prefix}{i}": set() for i in range(n)}
    vertices = list(succ)
    for u in vertices:
        for v in vertices:
            if u == v:
                continue
            if rng.random() <= p:
                succ[u].add(v)
    return DiGraph.from_successors(succ)


def path_graph(n: int, prefix: str = "P") -> DiGraph:
    if n <= 0:
        raise ValueError("path_graph requires n>0")
    succ = {}
    for i in range(n):
        u = f"{prefix}{i}"
        succ[u] = {f"{prefix}{i + 1}"} if i + 1 < n else set()
    return DiGraph.from_successors(succ)


def complete_bipartite(n_left: int, n_right: int, prefix_left: str = "L", prefix_right: str = "R") -> DiGraph:
    succ: Dict[str, Set[str]] = {}
    left = [f"{prefix_left}{i}" for i in range(n_left)]
    right = [f"{prefix_right}{i}" for i in range(n_right)]
    for u in left:
        succ[u] = set(right)
    for v in right:
        succ[v] = set(left)
    return DiGraph.from_successors(succ)


# ----------------------------------------------------------------------
# JSON helpers
# ----------------------------------------------------------------------
def graph_to_dict(graph: DiGraph) -> Dict[str, Dict[str, List[str]]]:
    return {"succ": graph.to_dict()}


def dict_to_graph(data: Dict[str, Dict[str, Iterable[str]]]) -> DiGraph:
    if "succ" not in data:
        raise ValueError("Invalid graph dictionary: missing 'succ'")
    return DiGraph.from_successors(data["succ"])


def load_json(path: str) -> DiGraph:
    with open(path, "r", encoding="utf8") as fh:
        data = json.load(fh)
    graph = dict_to_graph(data)
    graph.ensure_closed()
    return graph


def save_json(graph: DiGraph, path: str) -> None:
    with open(path, "w", encoding="utf8") as fh:
        json.dump(graph_to_dict(graph), fh, indent=2, sort_keys=True)
