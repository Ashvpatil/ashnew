"""Helpers for pruning symmetric branches."""
from __future__ import annotations

from typing import Dict, Iterable, List, Set

from ..engine.game import Move, Position
from ..engine.graphs import DiGraph


def orbit_map(graph: DiGraph) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    orbits = graph.approximate_symmetry_orbits()
    for idx, orbit in enumerate(orbits):
        for node in orbit:
            mapping[node] = idx
    # Nodes not part of any orbit receive unique identifiers.
    counter = len(orbits)
    for node in graph.successors:
        if node not in mapping:
            mapping[node] = counter
            counter += 1
    return mapping


def prune_symmetric_moves(position: Position, moves: Iterable[Move]) -> List[Move]:
    orbit_a = orbit_map(position.graph_a)
    orbit_b = orbit_map(position.graph_b)
    seen: Set[tuple] = set()
    result: List[Move] = []
    for move in moves:
        if move.graph == "A":
            orbit_source = orbit_a.get(move.source, -1)
            orbit_target = orbit_a.get(move.target, -1)
        else:
            orbit_source = orbit_b.get(move.source, -1)
            orbit_target = orbit_b.get(move.target, -1)
        key = (move.graph, move.move_type, orbit_source, orbit_target)
        if key in seen:
            continue
        seen.add(key)
        result.append(move)
    return result
