"""Witness trace generation for losing sequences."""
from __future__ import annotations

import json
from typing import Iterable, List

from ..engine.game import Move


def export_witness_trace(path: str, moves: Iterable[Move]) -> None:
    data = [
        {
            "graph": move.graph,
            "type": move.move_type,
            "source": move.source,
            "target": move.target,
        }
        for move in moves
    ]
    with open(path, "w", encoding="utf8") as fh:
        json.dump(data, fh, indent=2)
