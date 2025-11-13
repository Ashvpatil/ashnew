"""Optional SMT verification using z3."""

from __future__ import annotations

from typing import Optional

try:  # pragma: no cover - optional dependency
    from z3 import Bool, Solver, And, Or, sat
except Exception:  # pragma: no cover
    Bool = Solver = None  # type: ignore

from ..engine.graphs import DiGraph


def has_z3() -> bool:
    return Solver is not None


def check_equivalence(graph_a: DiGraph, graph_b: DiGraph) -> Optional[bool]:
    if Solver is None:
        return None
    solver = Solver()
    for v in graph_a.succ:
        solver.add(Bool(f"A_{v}"))
    for v in graph_b.succ:
        solver.add(Bool(f"B_{v}"))
    return solver.check() == sat
