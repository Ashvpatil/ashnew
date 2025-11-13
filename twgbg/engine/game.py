"""Core game rules and helper utilities for the bisimulation game."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .graphs import DiGraph

MoveType = str

MOVE_FORWARD: MoveType = "forward"
MOVE_BACKWARD: MoveType = "backward"
MOVE_JUMP: MoveType = "jump"
MOVE_TYPES: Tuple[MoveType, ...] = (MOVE_FORWARD, MOVE_BACKWARD, MOVE_JUMP)


@dataclass(frozen=True)
class Position:
    """Represents a full game state."""

    vertex_a: str
    vertex_b: str
    round_index: int = 0
    last_spoiler_graph: Optional[str] = None
    last_move_type: Optional[MoveType] = None
    jump_cooldown: int = 0
    jump_window: Tuple[int, ...] = field(default_factory=tuple)

    def next_round(self) -> int:
        return self.round_index + 1


@dataclass(frozen=True)
class Move:
    """A move chosen by Spoiler or Duplicator."""

    graph: str
    move_type: MoveType
    source: str
    target: str

    def __str__(self) -> str:  # pragma: no cover - human friendly output
        return f"{self.graph}:{self.move_type}:{self.source}->{self.target}"


class RuleSet:
    """Configuration flags controlling legal moves and optional variants."""

    def __init__(
        self,
        *,
        allow_backward: bool = True,
        allow_jump: bool = True,
        force_same_graph: Optional[str] = None,
        jump_cooldown: int = 0,
        jump_window: int = 0,
        jump_limit: Optional[int] = None,
        round_limit: Optional[int] = None,
        mirror_mode: bool = False,
    ) -> None:
        if force_same_graph not in (None, "A", "B"):
            raise ValueError("force_same_graph must be None, 'A' or 'B'")
        self.allow_backward = allow_backward
        self.allow_jump = allow_jump
        self.force_same_graph = force_same_graph
        self.jump_cooldown = max(0, int(jump_cooldown))
        self.jump_window = max(0, int(jump_window))
        self.jump_limit = jump_limit if jump_limit is None else max(0, int(jump_limit))
        self.round_limit = round_limit if round_limit is None else max(1, int(round_limit))
        self.mirror_mode = mirror_mode

    def legal_types(self, position: Optional[Position] = None) -> Tuple[MoveType, ...]:
        types: List[MoveType] = [MOVE_FORWARD]
        if self.allow_backward:
            types.append(MOVE_BACKWARD)
        if self.allow_jump and (position is None or self.jump_available(position)):
            types.append(MOVE_JUMP)
        return tuple(types)

    def allowed_sides(self, position: Position) -> Tuple[str, ...]:
        sides = ("A", "B")
        if self.force_same_graph:
            sides = (self.force_same_graph,)
        if self.mirror_mode and position.last_spoiler_graph:
            sides = tuple(side for side in sides if side != position.last_spoiler_graph)
        return sides

    def jump_available(self, position: Position) -> bool:
        if not self.allow_jump:
            return False
        if position.jump_cooldown > 0:
            return False
        if self.jump_limit is None or self.jump_window == 0:
            return True
        return sum(position.jump_window[-self.jump_window :]) < self.jump_limit

    def with_toggle(self, **kwargs: object) -> "RuleSet":
        options = {
            "allow_backward": self.allow_backward,
            "allow_jump": self.allow_jump,
            "force_same_graph": self.force_same_graph,
            "jump_cooldown": self.jump_cooldown,
            "jump_window": self.jump_window,
            "jump_limit": self.jump_limit,
            "round_limit": self.round_limit,
            "mirror_mode": self.mirror_mode,
        }
        options.update(kwargs)
        return RuleSet(**options)


def _iterate_sides(position: Position, graph_a: DiGraph, graph_b: DiGraph, rules: RuleSet):
    for name in rules.allowed_sides(position):
        if name == "A":
            yield name, graph_a, position.vertex_a
        elif name == "B":
            yield name, graph_b, position.vertex_b


def spoiler_legal_moves(
    graph_a: DiGraph, graph_b: DiGraph, position: Position, rules: RuleSet
) -> List[Move]:
    moves: List[Move] = []
    jump_enabled = rules.jump_available(position)
    for graph_name, graph, vertex in _iterate_sides(position, graph_a, graph_b, rules):
        for move_type in rules.legal_types(position):
            if move_type == MOVE_JUMP and not jump_enabled:
                continue
            if move_type == MOVE_FORWARD:
                for succ in graph.successors(vertex):
                    moves.append(Move(graph_name, move_type, vertex, succ))
            elif move_type == MOVE_BACKWARD:
                for pred in graph.predecessors(vertex):
                    moves.append(Move(graph_name, move_type, vertex, pred))
            elif move_type == MOVE_JUMP:
                for target in graph.vertices():
                    moves.append(Move(graph_name, move_type, vertex, target))
    return moves


def legal_responses(
    graph_a: DiGraph,
    graph_b: DiGraph,
    position: Position,
    spoiler_move: Move,
    rules: RuleSet,
) -> List[Move]:
    target_graph_name = "A" if spoiler_move.graph == "B" else "B"
    target_graph = graph_a if target_graph_name == "A" else graph_b
    current_vertex = position.vertex_a if target_graph_name == "A" else position.vertex_b

    replies: List[Move] = []
    if spoiler_move.move_type == MOVE_FORWARD:
        for succ in target_graph.successors(current_vertex):
            replies.append(Move(target_graph_name, MOVE_FORWARD, current_vertex, succ))
    elif spoiler_move.move_type == MOVE_BACKWARD:
        if rules.allow_backward:
            for pred in target_graph.predecessors(current_vertex):
                replies.append(Move(target_graph_name, MOVE_BACKWARD, current_vertex, pred))
    elif spoiler_move.move_type == MOVE_JUMP:
        if rules.allow_jump:
            for vertex in target_graph.vertices():
                replies.append(Move(target_graph_name, MOVE_JUMP, current_vertex, vertex))
    return replies


def step(
    graph_a: DiGraph,
    graph_b: DiGraph,
    position: Position,
    spoiler_move: Move,
    duplicator_move: Optional[Move],
    rules: Optional[RuleSet] = None,
) -> Tuple[Position, bool, Dict[str, object]]:
    if rules is None:
        rules = RuleSet()

    info: Dict[str, object] = {
        "spoiler_wins": False,
        "duplicator_survives": False,
    }

    if duplicator_move is None:
        info["spoiler_wins"] = True
        new_position = Position(
            position.vertex_a,
            position.vertex_b,
            round_index=position.next_round(),
            last_spoiler_graph=spoiler_move.graph,
            last_move_type=spoiler_move.move_type,
            jump_cooldown=rules.jump_cooldown if spoiler_move.move_type == MOVE_JUMP else max(0, position.jump_cooldown - 1),
            jump_window=_advance_jump_window(position.jump_window, spoiler_move, rules),
        )
        return new_position, False, info

    if spoiler_move.graph == "A":
        new_vertex_a = spoiler_move.target
        new_vertex_b = duplicator_move.target
    else:
        new_vertex_a = duplicator_move.target
        new_vertex_b = spoiler_move.target

    cooldown = max(0, position.jump_cooldown - 1)
    if spoiler_move.move_type == MOVE_JUMP:
        cooldown = rules.jump_cooldown

    jump_window = _advance_jump_window(position.jump_window, spoiler_move, rules)

    new_round = position.next_round()
    new_position = Position(
        new_vertex_a,
        new_vertex_b,
        round_index=new_round,
        last_spoiler_graph=spoiler_move.graph,
        last_move_type=spoiler_move.move_type,
        jump_cooldown=cooldown,
        jump_window=jump_window,
    )

    if rules.round_limit is not None and new_round >= rules.round_limit:
        info["duplicator_survives"] = True
        return new_position, False, info

    return new_position, True, info


def _advance_jump_window(
    previous: Sequence[int], spoiler_move: Move, rules: RuleSet
) -> Tuple[int, ...]:
    if rules.jump_window <= 0:
        return tuple()
    history = list(previous[-max(0, rules.jump_window - 1) :])
    history.append(1 if spoiler_move.move_type == MOVE_JUMP else 0)
    while len(history) < rules.jump_window:
        history.insert(0, 0)
    return tuple(history[-rules.jump_window :])


def is_terminal(
    graph_a: DiGraph,
    graph_b: DiGraph,
    position: Position,
    spoiler_move: Move,
    rules: RuleSet,
) -> bool:
    return not legal_responses(graph_a, graph_b, position, spoiler_move, rules)


def encode_position(position: Position) -> Tuple[str, str, int, Optional[str], Optional[MoveType]]:
    return (
        position.vertex_a,
        position.vertex_b,
        position.round_index,
        position.last_spoiler_graph,
        position.last_move_type,
    )


def decode_position(data: Tuple[str, str, int, Optional[str], Optional[MoveType]]) -> Position:
    vertex_a, vertex_b, round_index, last_graph, last_type = data
    return Position(vertex_a, vertex_b, round_index, last_graph, last_type)
