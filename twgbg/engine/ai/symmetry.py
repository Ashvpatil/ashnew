"""Symmetry reduction utilities."""
from __future__ import annotations

from typing import Tuple

from ..game import Position
from ..graphs import DiGraph


def canonical_position(graph_a: DiGraph, graph_b: DiGraph, pos: Position) -> Tuple[str, str]:
    """Return a canonical representation of the position.

    The canonical form sorts vertices by their signature partition class.  This
    is inexpensive and provides a mild reduction in the size of the search
    space for symmetric graphs.  The function is side-effect free and can be
    used as a hash key.
    """

    graph_a.partition_by_signature()
    graph_b.partition_by_signature()
    meta_a = graph_a.metadata(pos.vertex_a)
    meta_b = graph_b.metadata(pos.vertex_b)
    return (f"{meta_a.cluster}:{meta_a.label}", f"{meta_b.cluster}:{meta_b.label}")
