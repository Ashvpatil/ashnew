"""Bisimulation analysis helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from ..engine.graphs import DiGraph


def signature_partition(graph: DiGraph) -> Dict[str, List[str]]:
    """Compute simple signatures based on successor and predecessor multisets."""

    buckets: Dict[str, List[str]] = defaultdict(list)
    for v in graph.succ:
        succ_sig = ",".join(sorted(graph.succ[v]))
        pred_sig = ",".join(sorted(graph.pred[v]))
        sig = f"{succ_sig}|{pred_sig}"
        buckets[sig].append(v)
    return dict(buckets)
