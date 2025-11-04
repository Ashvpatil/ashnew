"""Optional Z3-based bisimulation checker."""
from __future__ import annotations

from typing import Dict, Tuple

from ..engine.graphs import DiGraph

try:  # pragma: no cover - optional dependency
    from z3 import Bool, And, Implies, Or, Solver, sat
except Exception:  # pragma: no cover - fallback when z3 missing
    Bool = None  # type: ignore
    Solver = None  # type: ignore


def check_bisimulation(graph_a: DiGraph, graph_b: DiGraph, node_a: str, node_b: str) -> bool:
    if Solver is None:
        raise RuntimeError("z3-solver not installed")
    solver = Solver()
    pairs = [(a, b) for a in graph_a.nodes() for b in graph_b.nodes()]
    relation: Dict[Tuple[str, str], object] = {(a, b): Bool(f"R_{a}_{b}") for a, b in pairs}

    for (a, b), var in relation.items():
        succ_a = list(graph_a.out_neighbours(a))
        succ_b = list(graph_b.out_neighbours(b))
        pred_a = list(graph_a.in_neighbours(a))
        pred_b = list(graph_b.in_neighbours(b))
        if succ_a:
            clauses = []
            for sa in succ_a:
                if succ_b:
                    clauses.append(Or([relation[(sa, sb)] for sb in succ_b]))
                else:
                    clauses.append(False)
            solver.add(Implies(var, And(clauses)))
        if succ_b:
            clauses = []
            for sb in succ_b:
                if succ_a:
                    clauses.append(Or([relation[(sa, sb)] for sa in succ_a]))
                else:
                    clauses.append(False)
            solver.add(Implies(var, And(clauses)))
        if pred_a:
            clauses = []
            for pa in pred_a:
                if pred_b:
                    clauses.append(Or([relation[(pa, pb)] for pb in pred_b]))
                else:
                    clauses.append(False)
            solver.add(Implies(var, And(clauses)))
        if pred_b:
            clauses = []
            for pb in pred_b:
                if pred_a:
                    clauses.append(Or([relation[(pa, pb)] for pa in pred_a]))
                else:
                    clauses.append(False)
            solver.add(Implies(var, And(clauses)))
    solver.add(relation[(node_a, node_b)])
    return solver.check() == sat
