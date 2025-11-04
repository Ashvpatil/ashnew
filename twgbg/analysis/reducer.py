"""Heuristic reducer for counterexample graphs."""
from __future__ import annotations

from typing import Tuple

from ..engine.game import Position, RuleSet, legal_responses, spoiler_legal_moves, step
from ..engine.graphs import DiGraph


def greedy_reduce(
    graph_a: DiGraph,
    graph_b: DiGraph,
    position: Position,
    rules: RuleSet,
    max_steps: int = 100,
) -> Tuple[DiGraph, DiGraph]:
    """Attempt to remove redundant vertices while preserving a Spoiler win."""

    reduced_a = graph_a.copy()
    reduced_b = graph_b.copy()
    for _ in range(max_steps):
        improved = False
        for is_a, graph in enumerate((reduced_a, reduced_b)):
            removable = [
                v
                for v in graph.vertices()
                if len(graph.successors(v)) <= 1 and len(graph.predecessors(v)) <= 1
            ]
            for vertex in removable:
                candidate = graph.copy()
                candidate.remove_vertex(vertex)
                candidate_a = candidate if is_a == 0 else reduced_a
                candidate_b = candidate if is_a == 1 else reduced_b
                if _spoiler_still_wins(candidate_a, candidate_b, position, rules):
                    if is_a == 0:
                        reduced_a = candidate
                    else:
                        reduced_b = candidate
                    improved = True
        if not improved:
            break
    return reduced_a, reduced_b


def _spoiler_still_wins(
    graph_a: DiGraph,
    graph_b: DiGraph,
    position: Position,
    rules: RuleSet,
) -> bool:
    for move in spoiler_legal_moves(graph_a, graph_b, position, rules):
        replies = legal_responses(graph_a, graph_b, position, move, rules)
        if not replies:
            return True
        if all(
            _spoiler_still_wins(
                graph_a,
                graph_b,
                step(graph_a, graph_b, position, move, reply, rules)[0],
                rules,
            )
            for reply in replies
        ):
            return True
    return False
