"""Core rules for the Two-Way Global Bisimulation Game."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

from .graphs import DiGraph

FORWARD = "forward"
BACKWARD = "backward"
JUMP = "jump"

MOVE_TYPES = (FORWARD, BACKWARD, JUMP)
SIDES = ("A", "B")


@dataclass(frozen=True)
class Position:
    """Represents the current vertices occupied on both graphs."""

    A_curr: str
    B_curr: str

    def swap(self) -> "Position":
        return Position(self.B_curr, self.A_curr)


@dataclass(frozen=True)
class Move:
    """Spoiler move description."""

    side: str
    mtype: str
    dest: str

    def notation(self) -> str:
        return f"{self.side}:{self.mtype}({self.dest})"


@dataclass
class RuleConfig:
    """Runtime configuration toggles controlling legal play."""

    allow_backward: bool = True
    allow_jump: bool = True
    force_same_graph: Optional[str] = None  # "A"/"B"
    jump_cooldown: Tuple[int, int] = (2, 5)
    round_limit: Optional[int] = None
    mirror_mode: bool = False
    seed: Optional[int] = None

    def key(self) -> Tuple:
        return (
            self.allow_backward,
            self.allow_jump,
            self.force_same_graph,
            self.jump_cooldown,
            self.round_limit,
            self.mirror_mode,
        )


@dataclass
class JumpWindow:
    """Tracks jump usage for the rolling window rule."""

    history: List[int] = field(default_factory=list)
    limit: Tuple[int, int] = (2, 5)

    def can_jump(self, round_number: int) -> bool:
        j, k = self.limit
        self._prune(round_number)
        return len(self.history) < j

    def record(self, round_number: int) -> None:
        self._prune(round_number)
        self.history.append(round_number)

    def _prune(self, round_number: int) -> None:
        j, k = self.limit
        lower = round_number - k + 1
        while self.history and self.history[0] < lower:
            self.history.pop(0)


def _mirror_target(round_number: int) -> str:
    return "A" if round_number % 2 == 0 else "B"


def _iter_move_targets(graph: DiGraph, base: str, *, allow_backward: bool, allow_jump: bool):
    for dest in sorted(graph.successors(base)):
        yield FORWARD, dest
    if allow_backward:
        for dest in sorted(graph.predecessors(base)):
            yield BACKWARD, dest
    if allow_jump:
        for dest in graph.vertices():
            if dest != base:
                yield JUMP, dest


def spoiler_legal_moves(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    config: RuleConfig,
    jump_window: Optional[JumpWindow],
    round_number: int,
) -> List[Move]:
    moves: List[Move] = []
    forced_side = config.force_same_graph
    sides = SIDES if forced_side is None else (forced_side,)
    if config.mirror_mode:
        sides = (_mirror_target(round_number),)

    for side in sides:
        base = pos.A_curr if side == "A" else pos.B_curr
        graph = graph_a if side == "A" else graph_b
        allow_jump = config.allow_jump and (jump_window is None or jump_window.can_jump(round_number))
        for mtype, dest in _iter_move_targets(graph, base, allow_backward=config.allow_backward, allow_jump=allow_jump):
            moves.append(Move(side=side, mtype=mtype, dest=dest))
    return moves


def legal_responses(graph: DiGraph, pos: Position, move: Move, config: RuleConfig) -> List[str]:
    base = pos.B_curr if move.side == "A" else pos.A_curr
    if move.mtype == FORWARD:
        return sorted(graph.successors(base))
    if move.mtype == BACKWARD:
        if not config.allow_backward:
            return []
        return sorted(graph.predecessors(base))
    if move.mtype == JUMP:
        if not config.allow_jump:
            return []
        return [v for v in graph.vertices() if v != base]
    raise ValueError(f"Unknown move type {move.mtype}")


def step(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    spoiler_move: Move,
    duplicator_reply: Optional[str],
    *,
    config: RuleConfig,
    jump_window: Optional[JumpWindow],
    round_number: int,
) -> Tuple[Position, bool, str]:
    if spoiler_move.side not in SIDES:
        raise ValueError("Invalid move side")
    if spoiler_move.mtype not in MOVE_TYPES:
        raise ValueError("Invalid move type")

    source_graph = graph_a if spoiler_move.side == "A" else graph_b
    target_graph = graph_b if spoiler_move.side == "A" else graph_a
    base = pos.A_curr if spoiler_move.side == "A" else pos.B_curr

    if spoiler_move.dest == base and spoiler_move.mtype == JUMP:
        raise ValueError("Spoiler cannot jump to the same vertex")

    if spoiler_move.mtype == FORWARD and spoiler_move.dest not in source_graph.successors(base):
        raise ValueError("Illegal forward move")
    if spoiler_move.mtype == BACKWARD:
        if not config.allow_backward:
            raise ValueError("Backward moves disabled")
        if spoiler_move.dest not in source_graph.predecessors(base):
            raise ValueError("Illegal backward move")
    if spoiler_move.mtype == JUMP and not config.allow_jump:
        raise ValueError("Jumps disabled")

    replies = legal_responses(target_graph, pos, spoiler_move, config)
    if not replies:
        info = f"Spoiler {spoiler_move.notation()} – Duplicator has no legal reply (Spoiler wins)"
        return pos, False, info

    if duplicator_reply is None or duplicator_reply not in replies:
        info = f"Duplicator supplied illegal reply to {spoiler_move.notation()} (Spoiler wins)"
        return pos, False, info

    if spoiler_move.side == "A":
        new_pos = Position(spoiler_move.dest, duplicator_reply)
    else:
        new_pos = Position(duplicator_reply, spoiler_move.dest)

    if spoiler_move.mtype == JUMP and jump_window is not None:
        jump_window.record(round_number)

    info = f"Spoiler {spoiler_move.notation()} | Duplicator->{duplicator_reply}"

    if config.round_limit is not None and round_number + 1 >= config.round_limit:
        info += " · Round limit reached (Duplicator wins)"
        return new_pos, False, info

    return new_pos, True, info


__all__ = [
    "Position",
    "Move",
    "RuleConfig",
    "JumpWindow",
    "spoiler_legal_moves",
    "legal_responses",
    "step",
]
