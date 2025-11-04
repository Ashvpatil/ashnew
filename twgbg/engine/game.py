"""Core game logic for the two-way global bisimulation game."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .graphs import DiGraph


MoveType = str


MOVE_FORWARD: MoveType = "forward"
MOVE_BACKWARD: MoveType = "backward"
MOVE_JUMP: MoveType = "jump"
MOVE_TYPES = (MOVE_FORWARD, MOVE_BACKWARD, MOVE_JUMP)


@dataclass(frozen=True)
class Position:
    """Represents the current vertices in both graphs."""

    vertex_a: str
    vertex_b: str


@dataclass(frozen=True)
class Move:
    """A move chosen by Spoiler or Duplicator."""

    graph: str  # "A" or "B" indicating the graph the move is made in
    move_type: MoveType
    source: str
    target: str

    def __str__(self) -> str:  # pragma: no cover - used mainly for logging
        return f"{self.graph}:{self.move_type}:{self.source}->{self.target}"


class RuleSet:
    """Configuration flags controlling legal moves."""

    def __init__(
        self,
        *,
        allow_backward: bool = True,
        allow_jump: bool = True,
        force_same_graph: bool = False,
    ) -> None:
        self.allow_backward = allow_backward
        self.allow_jump = allow_jump
        self.force_same_graph = force_same_graph

    def legal_types(self) -> Tuple[MoveType, ...]:
        types = [MOVE_FORWARD]
        if self.allow_backward:
            types.append(MOVE_BACKWARD)
        if self.allow_jump:
            types.append(MOVE_JUMP)
        return tuple(types)


def spoiler_legal_moves(graph_a: DiGraph, graph_b: DiGraph, pos: Position, rules: RuleSet) -> List[Move]:
    """Return all legal spoiler moves from the given position."""

    moves: List[Move] = []
    for graph_name, graph, vertex in (
        ("A", graph_a, pos.vertex_a),
        ("B", graph_b, pos.vertex_b),
    ):
        for move_type in rules.legal_types():
            if rules.force_same_graph and graph_name == "B":
                # Force Spoiler to always move in graph A
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
            else:  # pragma: no cover - defensive programming
                raise ValueError(f"unknown move type {move_type}")
    return moves


def legal_responses(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    spoiler_move: Move,
    rules: RuleSet,
) -> List[Move]:
    """Return all legal duplicator responses to the spoiler move."""

    target_graph_name = "A" if spoiler_move.graph == "B" else "B"
    target_graph = graph_a if target_graph_name == "A" else graph_b
    current_vertex = pos.vertex_a if target_graph_name == "A" else pos.vertex_b

    responses: List[Move] = []
    move_type = spoiler_move.move_type
    if move_type == MOVE_FORWARD:
        for succ in target_graph.successors(current_vertex):
            responses.append(Move(target_graph_name, move_type, current_vertex, succ))
    elif move_type == MOVE_BACKWARD and rules.allow_backward:
        for pred in target_graph.predecessors(current_vertex):
            responses.append(Move(target_graph_name, move_type, current_vertex, pred))
    elif move_type == MOVE_JUMP and rules.allow_jump:
        for target in target_graph.vertices():
            responses.append(Move(target_graph_name, move_type, current_vertex, target))
    return responses


def step(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    spoiler_move: Move,
    duplicator_move: Move,
) -> Position:
    """Advance the game state by applying the spoiler and duplicator moves."""

    if spoiler_move.graph == "A":
        new_a = spoiler_move.target
        new_b = duplicator_move.target
    else:
        new_a = duplicator_move.target
        new_b = spoiler_move.target
    return Position(new_a, new_b)


def is_terminal(
    graph_a: DiGraph,
    graph_b: DiGraph,
    pos: Position,
    spoiler_move: Move,
    rules: RuleSet,
) -> bool:
    """Return True if Spoiler wins immediately with the given move."""

    return not legal_responses(graph_a, graph_b, pos, spoiler_move, rules)


def encode_position(pos: Position) -> Tuple[str, str]:
    return pos.vertex_a, pos.vertex_b


def decode_position(data: Tuple[str, str]) -> Position:
    return Position(*data)
