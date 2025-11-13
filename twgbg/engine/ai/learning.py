"""Optional tabular value approximation used as a soft bias."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Tuple

from ..game import Position


@dataclass
class ValueTable:
    table: Dict[Tuple[int, int, int], float]

    @classmethod
    def from_json(cls, path: str) -> "ValueTable":
        with open(path, "r", encoding="utf8") as handle:
            data = json.load(handle)
        parsed = {
            tuple(map(int, key.split("-"))): float(value)
            for key, value in data.items()
        }
        return cls(parsed)

    def lookup(self, position: Position, indegree: int, outdegree: int) -> float:
        key = (position.round_index, indegree, outdegree)
        return self.table.get(key, 0.0)


def dump_value_table(path: str, table: Dict[Tuple[int, int, int], float]) -> None:
    serialised = {"-".join(map(str, key)): value for key, value in table.items()}
    with open(path, "w", encoding="utf8") as handle:
        json.dump(serialised, handle, indent=2, sort_keys=True)
