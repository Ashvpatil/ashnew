"""Simple tabular value bias used by the heuristic evaluators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from ..graphs import DiGraph


@dataclass
class ValueTable:
    values: Dict[str, float]

    def lookup(self, key: str) -> float:
        return self.values.get(key, 0.0)


def _features(graph_a: DiGraph, graph_b: DiGraph, a_curr: str | None, b_curr: str | None) -> str:
    return ";".join([
        str(len(graph_a.succ.get(a_curr or "", []))),
        str(len(graph_b.succ.get(b_curr or "", []))),
        str(len(graph_a.succ)),
        str(len(graph_b.succ)),
    ])


def load_table(path: str | Path) -> ValueTable:
    try:
        data = json.loads(Path(path).read_text(encoding="utf8"))
    except FileNotFoundError:
        data = {}
    return ValueTable({str(k): float(v) for k, v in data.items()})


def bias_value(table: ValueTable, graph_a: DiGraph, graph_b: DiGraph, a_curr: str | None, b_curr: str | None) -> float:
    key = _features(graph_a, graph_b, a_curr, b_curr)
    return table.lookup(key)
