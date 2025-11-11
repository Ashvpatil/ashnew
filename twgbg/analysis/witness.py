"""Witness extraction utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..engine.notation import Ply, serialize


@dataclass
class Witness:
    history: List[Ply]

    def to_text(self) -> str:
        return serialize(self.history)


__all__ = ["Witness"]
