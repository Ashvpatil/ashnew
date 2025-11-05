"""Compact notation similar to PGN for replaying games."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .game import Move


@dataclass
class NotationEntry:
    index: int
    spoiler: Move
    duplicator: Move

    def to_string(self) -> str:
        arrow = "→"
        return (
            f"{self.index}. {self.spoiler.side}:{self.spoiler.mtype}"
            f"({self.spoiler.dest}) {arrow} "
            f"{self.duplicator.side}:{self.duplicator.mtype}({self.duplicator.dest})"
        )


def serialize(history: Iterable[Move]) -> str:
    moves = list(history)
    entries: List[str] = []
    for i in range(0, len(moves), 2):
        spoiler = moves[i]
        duplicator = moves[i + 1] if i + 1 < len(moves) else Move("B", spoiler.mtype, None)
        entry = NotationEntry(i // 2 + 1, spoiler, duplicator)
        entries.append(entry.to_string())
    return " | ".join(entries)


def deserialize(text: str) -> List[Move]:
    if not text.strip():
        return []
    moves: List[Move] = []
    for chunk in text.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        prefix, reply = chunk.split("→")
        spoiler_part = prefix.split()[-1]
        dup_part = reply.strip()
        spoiler_side, rest = spoiler_part.split(":", 1)
        spoiler_type, spoiler_dest = rest.split("(")
        spoiler_dest = spoiler_dest.strip(") ") or None
        dup_side, dup_rest = dup_part.split(":", 1)
        dup_type, dup_dest = dup_rest.split("(")
        dup_dest = dup_dest.strip(") ") or None
        moves.append(Move(spoiler_side, spoiler_type, spoiler_dest))
        moves.append(Move(dup_side, dup_type, dup_dest))
    return moves
