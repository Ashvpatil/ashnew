"""Optional Z3 verification wrapper."""
from __future__ import annotations

try:  # pragma: no cover - optional dependency
    from z3 import Int, Solver, sat  # type: ignore
except Exception:  # pragma: no cover - keep runtime optional
    Int = None  # type: ignore
    Solver = None  # type: ignore
    sat = None  # type: ignore


def available() -> bool:
    return Solver is not None


__all__ = ["available"]
