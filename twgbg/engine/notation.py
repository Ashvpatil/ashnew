"""TWG-PGN style notation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .game import Move


@dataclass(frozen=True)
class Ply:
    """Represents a full Spoiler/duplicator exchange."""

    spoiler: Move
    duplicator: str

    def __str__(self) -> str:
        return f"{self.spoiler.side}:{self.spoiler.mtype}({self.spoiler.dest}) | {self.duplicator}"


def serialize(history: Sequence["Ply"]) -> str:
    return "\n".join(str(ply) for ply in history)


def parse(text: str) -> List["Ply"]:
    history: List[Ply] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            lhs, rhs = line.split("|")
            side, rest = lhs.split(":")
            mtype, dest = rest.split("(")
            dest = dest.rstrip(") ")
            reply = rhs.strip()
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid notation line: {line}") from exc
        history.append(Ply(Move(side.strip(), mtype.strip(), dest.strip()), reply))
    return history


__all__ = ["Ply", "serialize", "parse"]
