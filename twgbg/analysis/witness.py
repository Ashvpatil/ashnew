"""Witness extraction utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..engine.game import Move
from ..engine.notation import serialize
from ..engine.utils import json_dump


@dataclass
class Witness:
    history: List[Move]

    def to_notation(self) -> str:
        return serialize(self.history)

    def to_json(self) -> dict:
        return {"notation": self.to_notation()}

    def export(self, path: str) -> None:
        json_dump(self.to_json(), path)


def minimal_witness(history: Iterable[Move]) -> Witness:
    return Witness(list(history))
