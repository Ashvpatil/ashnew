"""Optional verification using Z3."""
from __future__ import annotations

from typing import Optional

from ..engine.graphs import DiGraph


def check_bisimulation(graph_a: DiGraph, graph_b: DiGraph) -> Optional[bool]:
    try:
        from z3 import Bool, And, Implies, Solver
    except Exception:  # pragma: no cover - optional dependency
        return None

    solver = Solver()
    vertices_a = graph_a.vertices()
    vertices_b = graph_b.vertices()
    relation = {
        (a, b): Bool(f"R_{a}_{b}")
        for a in vertices_a
        for b in vertices_b
    }
    constraints = []
    for a in vertices_a:
        for b in vertices_b:
            ra = graph_a.successors(a)
            rb = graph_b.successors(b)
            la = [relation[(sa, sb)] for sa in ra for sb in rb]
            if la:
                constraints.append(Implies(relation[(a, b)], And(la)))
    solver.add(constraints)
    if solver.check() == 1:
        return True
    return False
