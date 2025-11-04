"""Graph utilities for the Two-Way Global Bisimulation Game.

This module exposes a light-weight directed graph implementation tailored to
bisimulation-style reasoning.  It deliberately avoids heavy dependencies while
supporting deterministic behaviour and serialisation helpers that make the
engine and GUI code easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, MutableMapping, Optional, Sequence, Set, Tuple
import json
import math
import random


Node = str


@dataclass
class DiGraph:
    """Simple deterministic directed graph with predecessor/successor caches.

    The class stores both successor and predecessor adjacency maps so that
    forward and backward moves are equally cheap.  Nodes are represented as
    strings which keeps serialisation straightforward and avoids surprises when
    graphs are saved to JSON.
    """

    successors: MutableMapping[Node, Set[Node]] = field(default_factory=dict)
    predecessors: MutableMapping[Node, Set[Node]] = field(default_factory=dict)

    def copy(self) -> "DiGraph":
        return DiGraph(
            successors={k: set(v) for k, v in self.successors.items()},
            predecessors={k: set(v) for k, v in self.predecessors.items()},
        )

    # ------------------------------------------------------------------
    # node/edge management
    # ------------------------------------------------------------------
    def add_node(self, node: Node) -> None:
        if node not in self.successors:
            self.successors[node] = set()
            self.predecessors[node] = set()

    def add_edge(self, source: Node, target: Node) -> None:
        self.add_node(source)
        self.add_node(target)
        if target not in self.successors[source]:
            self.successors[source].add(target)
            self.predecessors[target].add(source)

    def remove_edge(self, source: Node, target: Node) -> None:
        if source in self.successors and target in self.successors[source]:
            self.successors[source].remove(target)
            self.predecessors[target].remove(source)

    def remove_node(self, node: Node) -> None:
        if node not in self.successors:
            return
        for tgt in list(self.successors[node]):
            self.predecessors[tgt].remove(node)
        for src in list(self.predecessors[node]):
            self.successors[src].remove(node)
        del self.successors[node]
        del self.predecessors[node]

    # ------------------------------------------------------------------
    # iteration helpers
    # ------------------------------------------------------------------
    def nodes(self) -> Iterator[Node]:
        return iter(self.successors.keys())

    def edges(self) -> Iterator[Tuple[Node, Node]]:
        for src, succs in self.successors.items():
            for tgt in succs:
                yield src, tgt

    def out_neighbours(self, node: Node) -> Set[Node]:
        return self.successors.get(node, set())

    def in_neighbours(self, node: Node) -> Set[Node]:
        return self.predecessors.get(node, set())

    def __contains__(self, node: Node) -> bool:  # pragma: no cover - trivial
        return node in self.successors

    def __len__(self) -> int:
        return len(self.successors)

    # ------------------------------------------------------------------
    # serialisation helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, List[str]]:
        return {node: sorted(list(targets)) for node, targets in self.successors.items()}

    @classmethod
    def from_dict(cls, payload: MutableMapping[str, Iterable[str]]) -> "DiGraph":
        graph = cls()
        for node, targets in payload.items():
            for target in targets:
                graph.add_edge(node, target)
            if not targets:
                graph.add_node(node)
        for node in payload.keys():
            graph.add_node(node)
        return graph

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "DiGraph":
        return cls.from_dict(json.loads(text))

    # ------------------------------------------------------------------
    # graph generation utilities
    # ------------------------------------------------------------------
    @classmethod
    def random_graph(
        cls,
        num_vertices: int,
        edge_probability: float,
        seed: Optional[int] = None,
        prefix: str = "v",
    ) -> "DiGraph":
        rng = random.Random(seed)
        graph = cls()
        for idx in range(num_vertices):
            graph.add_node(f"{prefix}{idx}")
        for src in list(graph.nodes()):
            for tgt in list(graph.nodes()):
                if src == tgt:
                    continue
                if rng.random() < edge_probability:
                    graph.add_edge(src, tgt)
        return graph

    def signature(self, node: Node) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """Return the structural signature used in partition diagnostics."""
        succ_sig = tuple(sorted(self.successors.get(node, [])))
        pred_sig = tuple(sorted(self.predecessors.get(node, [])))
        return succ_sig, pred_sig

    def partitions(self) -> Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], List[Node]]:
        partitions: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], List[Node]] = {}
        for node in self.successors:
            sig = self.signature(node)
            partitions.setdefault(sig, []).append(node)
        return partitions

    def hashable_view(self) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
        """Return a canonical-ish tuple for caching positions.

        The representation sorts nodes and outgoing edges.  It is not a fully
        canonical isomorphism invariant but works well for transposition table
        lookups within a fixed labelling.
        """

        items = []
        for node in sorted(self.successors.keys()):
            items.append((node, tuple(sorted(self.successors[node]))))
        return tuple(items)

    # ------------------------------------------------------------------
    # similarity utilities
    # ------------------------------------------------------------------
    def approximate_symmetry_orbits(self) -> List[Set[Node]]:
        """Group nodes by degree sequence heuristics.

        This is intentionally light-weight: full graph automorphism would be
        expensive and unnecessary for small graphs.  We instead cluster nodes by
        their in/out degrees and signature hashes.  The caller can then treat
        nodes inside the same orbit as approximately symmetric for pruning
        purposes.
        """

        buckets: Dict[Tuple[int, int, int], Set[Node]] = {}
        for node in self.successors:
            succ = self.successors[node]
            pred = self.predecessors[node]
            key = (len(succ), len(pred), hash(self.signature(node)))
            buckets.setdefault(key, set()).add(node)
        return [bucket for bucket in buckets.values() if len(bucket) > 1]

    def describe(self) -> str:
        """Human readable multi-line description useful for debugging."""

        lines = ["digraph {"]
        for node in sorted(self.successors):
            lines.append(f"  {node} [out={len(self.successors[node])} in={len(self.predecessors[node])}]")
            for tgt in sorted(self.successors[node]):
                lines.append(f"  {node} -> {tgt}")
        lines.append("}")
        return "\n".join(lines)


def graph_distance(g1: DiGraph, g2: DiGraph) -> float:
    """Compute a simple structural distance metric between two graphs."""

    if len(g1) == 0 and len(g2) == 0:
        return 0.0
    all_nodes = set(g1.successors) | set(g2.successors)
    total = 0
    for node in all_nodes:
        succ1 = g1.successors.get(node, set())
        succ2 = g2.successors.get(node, set())
        pred1 = g1.predecessors.get(node, set())
        pred2 = g2.predecessors.get(node, set())
        total += len(succ1 ^ succ2) + len(pred1 ^ pred2)
    denom = max(1, sum(len(g.successors) + sum(len(v) for v in g.successors.values()) for g in (g1, g2)))
    return total / denom
