"""Graph utilities for the Two-Way Global Bisimulation Game.

This module provides a light-weight directed graph implementation that
supports the functionality required by the game engine and the GUI.  The
implementation intentionally avoids dependencies outside of the standard
library so that the logic layer can be reused in non-GUI contexts such as
tests or command line experiments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple
import json
import math
import random


MoveType = str


@dataclass
class VertexMetadata:
    """Metadata attached to vertices.

    The GUI uses this to show tooltips and high level statistics.  The
    analytics routines also reuse the values.
    """

    label: str
    signature: Optional[str] = None
    cluster: Optional[int] = None
    payload: Dict[str, object] = field(default_factory=dict)


class DiGraph:
    """A simple adjacency-list based directed graph."""

    def __init__(self, name: str = "", seed: Optional[int] = None) -> None:
        self.name = name
        self._succ: Dict[str, Set[str]] = {}
        self._pred: Dict[str, Set[str]] = {}
        self._metadata: Dict[str, VertexMetadata] = {}
        self.random = random.Random(seed)

    # ------------------------------------------------------------------
    # Basic manipulation
    # ------------------------------------------------------------------
    def add_vertex(self, vertex: str, *, label: Optional[str] = None) -> None:
        vertex = str(vertex)
        if vertex not in self._succ:
            self._succ[vertex] = set()
            self._pred[vertex] = set()
            self._metadata[vertex] = VertexMetadata(label or vertex)

    def remove_vertex(self, vertex: str) -> None:
        if vertex not in self._succ:
            return
        for pred in list(self._pred[vertex]):
            self._succ[pred].discard(vertex)
        for succ in list(self._succ[vertex]):
            self._pred[succ].discard(vertex)
        self._succ.pop(vertex, None)
        self._pred.pop(vertex, None)
        self._metadata.pop(vertex, None)

    def add_edge(self, u: str, v: str) -> None:
        self.add_vertex(u)
        self.add_vertex(v)
        self._succ[u].add(v)
        self._pred[v].add(u)

    def remove_edge(self, u: str, v: str) -> None:
        self._succ.get(u, set()).discard(v)
        self._pred.get(v, set()).discard(u)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def vertices(self) -> List[str]:
        return list(self._succ.keys())

    def edges(self) -> List[Tuple[str, str]]:
        return [(u, v) for u, vs in self._succ.items() for v in vs]

    def successors(self, u: str) -> Set[str]:
        return set(self._succ.get(u, set()))

    def predecessors(self, u: str) -> Set[str]:
        return set(self._pred.get(u, set()))

    def degree(self, u: str) -> Tuple[int, int]:
        return len(self._pred.get(u, set())), len(self._succ.get(u, set()))

    def metadata(self, u: str) -> VertexMetadata:
        key = str(u)
        if key not in self._metadata:
            self._metadata[key] = VertexMetadata(key)
            self._succ.setdefault(key, set())
            self._pred.setdefault(key, set())
        return self._metadata[key]

    def set_metadata(self, u: str, **kwargs: object) -> None:
        data = self._metadata[u]
        for key, value in kwargs.items():
            setattr(data, key, value)

    def rename_vertex(self, old: str, new: str) -> None:
        if old == new:
            return
        if new in self._succ:
            raise ValueError(f"vertex {new!r} already exists")
        self._succ[new] = self._succ.pop(old, set())
        self._pred[new] = self._pred.pop(old, set())
        self._metadata[new] = self._metadata.pop(old)
        for pred in self._pred[new]:
            succ = self._succ[pred]
            if old in succ:
                succ.remove(old)
                succ.add(new)
        for succ in self._succ[new]:
            pred = self._pred[succ]
            if old in pred:
                pred.remove(old)
                pred.add(new)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    @classmethod
    def erdos_renyi(
        cls,
        n: int,
        p: float,
        *,
        allow_self_loops: bool = False,
        seed: Optional[int] = None,
        name: str = "Erdos-Renyi",
    ) -> "DiGraph":
        """Generate a random graph using the Erdős–Rényi G(n, p) model."""

        if not 0.0 <= p <= 1.0:
            raise ValueError("p must be in [0, 1]")
        graph = cls(name=name, seed=seed)
        for i in range(n):
            graph.add_vertex(str(i))
        rng = graph.random
        for i in range(n):
            for j in range(n):
                if i == j and not allow_self_loops:
                    continue
                if rng.random() <= p:
                    graph.add_edge(str(i), str(j))
        return graph

    @classmethod
    def path(cls, n: int, *, name: str = "Path") -> "DiGraph":
        graph = cls(name=name)
        for i in range(n):
            graph.add_vertex(str(i))
            if i > 0:
                graph.add_edge(str(i - 1), str(i))
        return graph

    # ------------------------------------------------------------------
    # JSON serialisation
    # ------------------------------------------------------------------
    def to_json(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "vertices": [
                {
                    "id": v,
                    "label": self._metadata[v].label,
                    "signature": self._metadata[v].signature,
                    "cluster": self._metadata[v].cluster,
                    "payload": self._metadata[v].payload,
                }
                for v in self._succ
            ],
            "edges": [(u, v) for u in self._succ for v in self._succ[u]],
        }

    @classmethod
    def from_json(cls, data: Dict[str, object]) -> "DiGraph":
        graph = cls(name=str(data.get("name", "")))
        for vertex in data.get("vertices", []):
            vid = str(vertex["id"])
            graph.add_vertex(vid, label=str(vertex.get("label", vid)))
            meta = graph.metadata(vid)
            meta.signature = vertex.get("signature")
            meta.cluster = vertex.get("cluster")
            meta.payload.update(vertex.get("payload", {}))
        for u, v in data.get("edges", []):
            graph.add_edge(str(u), str(v))
        return graph

    def dump_json(self, path: str) -> None:
        with open(path, "w", encoding="utf8") as fh:
            json.dump(self.to_json(), fh, indent=2, sort_keys=True)

    @classmethod
    def load_json(cls, path: str) -> "DiGraph":
        with open(path, "r", encoding="utf8") as fh:
            data = json.load(fh)
        return cls.from_json(data)

    # ------------------------------------------------------------------
    # Signature helper used by the analysis tools and heuristics.
    # ------------------------------------------------------------------
    def compute_signatures(self) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]:
        """Return successor/predecessor signature tuples for each vertex."""

        signatures: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {}
        for v in self._succ:
            succ_sig = tuple(sorted(self._succ[v]))
            pred_sig = tuple(sorted(self._pred[v]))
            signatures[v] = (succ_sig, pred_sig)
            self._metadata[v].signature = f"S:{len(succ_sig)} P:{len(pred_sig)}"
        return signatures

    def partition_by_signature(self) -> Dict[str, int]:
        sigs = self.compute_signatures()
        signature_to_class: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], int] = {}
        classes: Dict[str, int] = {}
        for vertex, sig in sigs.items():
            if sig not in signature_to_class:
                signature_to_class[sig] = len(signature_to_class)
            classes[vertex] = signature_to_class[sig]
            self._metadata[vertex].cluster = classes[vertex]
        return classes

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def copy(self) -> "DiGraph":
        return DiGraph.from_json(self.to_json())

    def __len__(self) -> int:
        return len(self._succ)

    def __contains__(self, vertex: str) -> bool:
        return vertex in self._succ


def load_graph_pair(path: str) -> Tuple[DiGraph, DiGraph]:
    """Load a pair of graphs stored in a JSON structure."""

    with open(path, "r", encoding="utf8") as fh:
        data = json.load(fh)
    graph_a = DiGraph.from_json(data["graph_a"])
    graph_b = DiGraph.from_json(data["graph_b"])
    return graph_a, graph_b


def save_graph_pair(path: str, graph_a: DiGraph, graph_b: DiGraph) -> None:
    with open(path, "w", encoding="utf8") as fh:
        json.dump({"graph_a": graph_a.to_json(), "graph_b": graph_b.to_json()}, fh, indent=2)
