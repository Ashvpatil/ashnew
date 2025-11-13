"""Directed graph helpers used by the bisimulation game."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, MutableMapping, Optional, Set

from .utils import DeterministicRNG, json_dump, json_load


@dataclass
class DiGraph:
    """Simple adjacency based directed graph."""

    succ: MutableMapping[str, Set[str]] = field(default_factory=dict)
    pred: MutableMapping[str, Set[str]] = field(default_factory=dict)

    def add_vertex(self, v: str) -> None:
        if v not in self.succ:
            self.succ[v] = set()
        if v not in self.pred:
            self.pred[v] = set()

    def add_edge(self, u: str, v: str) -> None:
        self.add_vertex(u)
        self.add_vertex(v)
        self.succ[u].add(v)
        self.pred[v].add(u)

    def remove_vertex(self, v: str) -> None:
        for p in list(self.pred.get(v, [])):
            self.succ[p].discard(v)
        for s in list(self.succ.get(v, [])):
            self.pred[s].discard(v)
        self.succ.pop(v, None)
        self.pred.pop(v, None)

    def remove_edge(self, u: str, v: str) -> None:
        self.succ.get(u, set()).discard(v)
        self.pred.get(v, set()).discard(u)

    def vertices(self) -> Iterator[str]:
        return iter(self.succ.keys())

    def successors(self, v: str) -> Set[str]:
        return set(self.succ.get(v, set()))

    def predecessors(self, v: str) -> Set[str]:
        return set(self.pred.get(v, set()))

    def to_dict(self, start: Optional[str] = None) -> Dict[str, object]:
        return {
            "succ": {k: sorted(v) for k, v in self.succ.items()},
            "start": start,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "DiGraph":
        graph = cls()
        succ: Dict[str, Iterable[str]] = data.get("succ", {})  # type: ignore[assignment]
        for u, vs in succ.items():
            for v in vs:
                graph.add_edge(str(u), str(v))
        for v in list(graph.succ):
            graph.add_vertex(v)
        return graph

    def copy(self) -> "DiGraph":
        new_graph = DiGraph()
        for u in self.succ:
            new_graph.add_vertex(u)
        for u, vs in self.succ.items():
            for v in vs:
                new_graph.add_edge(u, v)
        return new_graph


def random_digraph(
    n: int,
    p: float,
    prefix: str = "V",
    seed: Optional[int] = None,
) -> tuple[DiGraph, str]:
    rng = DeterministicRNG(seed)
    g = DiGraph()
    verts = [f"{prefix}{i}" for i in range(1, n + 1)]
    for v in verts:
        g.add_vertex(v)
    for u in verts:
        for v in verts:
            if u == v:
                continue
            if rng.random() < p:
                g.add_edge(u, v)
    start = rng.choice(verts) if verts else ""
    return g, start


def path_graph(n: int, prefix: str = "P") -> tuple[DiGraph, str]:
    g = DiGraph()
    prev = None
    start = ""
    for i in range(1, n + 1):
        v = f"{prefix}{i}"
        g.add_vertex(v)
        if prev is not None:
            g.add_edge(prev, v)
        else:
            start = v
        prev = v
    return g, start


def dict_to_graph(data: Dict[str, object]) -> tuple[DiGraph, Optional[str]]:
    graph = DiGraph.from_dict(data)
    start = data.get("start")
    return graph, str(start) if start is not None else None


def graph_to_dict(graph: DiGraph, start: Optional[str] = None) -> Dict[str, object]:
    return graph.to_dict(start=start)


def load_json(path: str | Path) -> tuple[DiGraph, Optional[str]]:
    data = json_load(path)
    return dict_to_graph(data)


def save_json(graph: DiGraph, path: str | Path, start: Optional[str] = None) -> None:
    json_dump(graph_to_dict(graph, start=start), path)


def normalize_labels_to_str(graph: DiGraph) -> DiGraph:
    mapping = {v: str(v) for v in graph.vertices()}
    new = DiGraph()
    for v in mapping.values():
        new.add_vertex(v)
    for u, vs in graph.succ.items():
        for v in vs:
            new.add_edge(mapping[u], mapping[v])
    return new
