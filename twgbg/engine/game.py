"""Core rules for the Two-Way Global Bisimulation Game."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from .graphs import DiGraph

MoveType = str
Side = str


@dataclass(frozen=True)
class Position:
    """Current pair of vertices in the game."""

    A_curr: Optional[str]
    B_curr: Optional[str]


@dataclass(frozen=True)
class Move:
    """Representation of a single spoiler move or response."""

    side: Side  # 'A' or 'B'
    mtype: MoveType  # 'forward', 'backward', 'jump'
    dest: Optional[str]

    def __str__(self) -> str:  # pragma: no cover - human readable helper
        return f"{self.side}:{self.mtype}->{self.dest}"


@dataclass
class RuleConfig:
    allow_backward: bool = True
    allow_jump: bool = True
    force_same_graph: Optional[str] = None
    jump_cooldown: tuple[int, int] = (2, 5)
    round_limit: Optional[int] = None
    mirror_mode: bool = False
    rnd_seed: Optional[int] = None

    def within_jump_budget(self, history: Sequence[Move], new_move: Move) -> bool:
        if new_move.mtype != "jump":
            return True
        J, K = self.jump_cooldown
        if K <= 0:
            return J > 0
        recent = [m for m in history[-K:] if m.mtype == "jump"]
        return len(recent) < J


@dataclass
class GameState:
    """Convenience bundle tracked by the GUI."""

    graph_a: DiGraph
    graph_b: DiGraph
    position: Position
    history: List[Move] = field(default_factory=list)
    round_no: int = 0
    spoiler_last_side: Optional[str] = None


def spoiler_legal_moves(
    graph: DiGraph,
    pos: str | None,
    allow_backward: bool,
    allow_jump: bool,
) -> List[Move]:
    moves: List[Move] = []
    if pos is None:
        return moves
    for succ in sorted(graph.successors(pos)):
        moves.append(Move("A", "forward", succ))
    if allow_backward:
        for pred in sorted(graph.predecessors(pos)):
            moves.append(Move("A", "backward", pred))
    if allow_jump:
        for v in sorted(graph.succ.keys()):
            if v != pos:
                moves.append(Move("A", "jump", v))
    return moves


def legal_responses(
    graph: DiGraph,
    pos: str | None,
    mtype: MoveType,
) -> List[str]:
    if pos is None:
        return []
    if mtype == "forward":
        return sorted(graph.successors(pos))
    if mtype == "backward":
        return sorted(graph.predecessors(pos))
    if mtype == "jump":
        return sorted(v for v in graph.succ if v != pos)
    raise ValueError(f"unknown move type {mtype}")


def _other(side: str) -> str:
    return "B" if side == "A" else "A"


def step(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    spoiler_move: Move,
    duplicator_reply: Optional[str],
    *,
    config: RuleConfig,
    history: Optional[List[Move]] = None,
    round_no: int = 0,
    spoiler_last_side: Optional[str] = None,
) -> tuple[Position, bool, str, Optional[str]]:
    """Advance the game by a single round.

    Returns the new position, alive flag (duplicator can continue) and info message
    together with the resolved duplicator node when applicable.
    """

    history = history or []
    info = ""

    if config.force_same_graph in {"A", "B"} and spoiler_move.side != config.force_same_graph:
        return pos, False, "Spoiler must play on forced graph", None

    if config.mirror_mode and spoiler_last_side and spoiler_move.side == spoiler_last_side:
        return pos, False, "Mirror mode requires alternating graphs", None

    if not config.within_jump_budget(history, spoiler_move):
        return pos, False, "Jump cooldown exhausted", None

    if spoiler_move.side == "A":
        graph = graph_a
        current = pos.A_curr
        other_graph = graph_b
        other_current = pos.B_curr
    else:
        graph = graph_b
        current = pos.B_curr
        other_graph = graph_a
        other_current = pos.A_curr

    legal = spoiler_legal_moves(
        graph,
        current,
        allow_backward=config.allow_backward,
        allow_jump=config.allow_jump,
    )
    if not any(m.mtype == spoiler_move.mtype and m.dest == spoiler_move.dest for m in legal):
        return pos, False, "Illegal spoiler move", None

    responses = legal_responses(other_graph, other_current, spoiler_move.mtype)
    if duplicator_reply is None or duplicator_reply not in responses:
        return pos, False, "Duplicator has no legal reply", None

    if spoiler_move.side == "A":
        new_pos = Position(spoiler_move.dest, duplicator_reply)
    else:
        new_pos = Position(duplicator_reply, spoiler_move.dest)

    new_history = history + [
        Move(spoiler_move.side, spoiler_move.mtype, spoiler_move.dest),
        Move(_other(spoiler_move.side), spoiler_move.mtype, duplicator_reply),
    ]

    info = f"Spoiler {spoiler_move.mtype} to {spoiler_move.dest}; Duplicator -> {duplicator_reply}"

    if config.round_limit is not None and round_no + 1 >= config.round_limit:
        return new_pos, False, "Round limit reached - Duplicator survives", duplicator_reply

    return new_pos, True, info, duplicator_reply
