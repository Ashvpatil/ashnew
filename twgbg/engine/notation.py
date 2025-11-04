"""Notation helpers for logging and replay files."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .game import MOVE_BACKWARD, MOVE_FORWARD, MOVE_JUMP, Move

TURN_SEPARATOR = " | "


@dataclass
class AnnotatedTurn:
    spoiler: Move
    duplicator: Move

    def to_text(self) -> str:
        return f"{format_move(self.spoiler)} || {format_move(self.duplicator)}"


def format_move(move: Move) -> str:
    prefix = move.graph
    if move.move_type == MOVE_FORWARD:
        verb = "→"
    elif move.move_type == MOVE_BACKWARD:
        verb = "←"
    elif move.move_type == MOVE_JUMP:
        verb = "⇢"
    else:  # pragma: no cover - defensive fallback
        verb = "?"
    return f"{prefix}:{move.source}{verb}{move.target}"


def encode_history(history: Sequence[Move], replies: Sequence[Move]) -> str:
    turns: List[str] = []
    for spoiler, duplicator in zip(history, replies):
        turns.append(f"{format_move(spoiler)} || {format_move(duplicator)}")
    return TURN_SEPARATOR.join(turns)


def decode_history(serialised: str) -> Tuple[List[Move], List[Move]]:
    spoiler_moves: List[Move] = []
    duplicator_moves: List[Move] = []
    if not serialised.strip():
        return spoiler_moves, duplicator_moves
    for turn in serialised.split(TURN_SEPARATOR):
        spoiler_text, dup_text = [part.strip() for part in turn.split("||", 1)]
        spoiler_moves.append(parse_move(spoiler_text))
        duplicator_moves.append(parse_move(dup_text))
    return spoiler_moves, duplicator_moves


def parse_move(text: str) -> Move:
    graph, payload = text.split(":", 1)
    if "⇢" in payload:
        source, target = payload.split("⇢")
        move_type = MOVE_JUMP
    elif "→" in payload:
        source, target = payload.split("→")
        move_type = MOVE_FORWARD
    elif "←" in payload:
        source, target = payload.split("←")
        move_type = MOVE_BACKWARD
    else:
        raise ValueError(f"Invalid move text: {text}")
    return Move(graph.strip(), move_type, source.strip(), target.strip())


def export_replay(path: str, history: Sequence[Move], replies: Sequence[Move]) -> None:
    with open(path, "w", encoding="utf8") as handle:
        handle.write(encode_history(history, replies))


def import_replay(path: str) -> Tuple[List[Move], List[Move]]:
    with open(path, "r", encoding="utf8") as handle:
        return decode_history(handle.read())
