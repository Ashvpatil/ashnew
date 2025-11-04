"""Core game logic for the Two-Way Global Bisimulation Game."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .graphs import DiGraph

MoveType = str  # forward/backward/jump
GraphChoice = str  # 'A' or 'B'


@dataclass(frozen=True)
class Move:
    """Representation of a single move in the game."""

    graph: GraphChoice
    move_type: MoveType
    source: str
    target: str

    def describe(self) -> str:
        arrow = {
            "forward": "→",
            "backward": "←",
            "jump": "⇢",
        }[self.move_type]
        return f"{self.graph}:{self.source} {arrow} {self.target}"


@dataclass
class Position:
    graph_a: DiGraph
    graph_b: DiGraph
    node_a: str
    node_b: str
    allow_backward: bool = True
    allow_jump: bool = True
    force_same_graph: Optional[GraphChoice] = None
    move_history: List[Move] = None
    spoiler_turn: bool = True

    def __post_init__(self) -> None:
        if self.node_a not in self.graph_a:
            raise ValueError(f"node {self.node_a} not in graph A")
        if self.node_b not in self.graph_b:
            raise ValueError(f"node {self.node_b} not in graph B")
        if self.move_history is None:
            self.move_history = []

    # ------------------------------------------------------------------
    def clone(self) -> "Position":
        return Position(
            graph_a=self.graph_a.copy(),
            graph_b=self.graph_b.copy(),
            node_a=self.node_a,
            node_b=self.node_b,
            allow_backward=self.allow_backward,
            allow_jump=self.allow_jump,
            force_same_graph=self.force_same_graph,
            move_history=list(self.move_history),
            spoiler_turn=self.spoiler_turn,
        )

    # ------------------------------------------------------------------
    def spoiler_legal_moves(self) -> List[Move]:
        """Enumerate all legal Spoiler moves from the current position."""

        moves: List[Move] = []
        graphs = {"A": (self.graph_a, self.node_a), "B": (self.graph_b, self.node_b)}
        for graph_name, (graph, node) in graphs.items():
            if self.force_same_graph and graph_name != self.force_same_graph:
                continue
            if self.allow_backward:
                for pred in graph.in_neighbours(node):
                    moves.append(Move(graph=graph_name, move_type="backward", source=node, target=pred))
            for succ in graph.out_neighbours(node):
                moves.append(Move(graph=graph_name, move_type="forward", source=node, target=succ))
            if self.allow_jump:
                for other in graph.nodes():
                    if other != node:
                        moves.append(Move(graph=graph_name, move_type="jump", source=node, target=other))
        return moves

    # ------------------------------------------------------------------
    def legal_responses(self, spoiler_move: Move) -> List[Move]:
        """Enumerate Duplicator replies consistent with the Spoiler move."""

        if spoiler_move.graph == "A":
            graph = self.graph_b
            node = self.node_b
            response_graph = "B"
        else:
            graph = self.graph_a
            node = self.node_a
            response_graph = "A"

        moves: List[Move] = []
        if spoiler_move.move_type == "forward":
            for succ in graph.out_neighbours(node):
                moves.append(Move(response_graph, "forward", node, succ))
        elif spoiler_move.move_type == "backward":
            if not self.allow_backward:
                return []
            for pred in graph.in_neighbours(node):
                moves.append(Move(response_graph, "backward", node, pred))
        elif spoiler_move.move_type == "jump":
            if not self.allow_jump:
                return []
            for other in graph.nodes():
                if other != node:
                    moves.append(Move(response_graph, "jump", node, other))
        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown move type {spoiler_move.move_type}")
        return moves

    # ------------------------------------------------------------------
    def step(self, spoiler_move: Move, duplicator_reply: Move) -> "Position":
        """Advance the game state by one pair of moves."""

        if duplicator_reply.graph == spoiler_move.graph:
            raise ValueError("Duplicator must play in the other graph")
        new_state = self.clone()
        new_state.move_history.append(spoiler_move)
        new_state.move_history.append(duplicator_reply)
        if spoiler_move.graph == "A":
            new_state.node_a = spoiler_move.target
            new_state.node_b = duplicator_reply.target
        else:
            new_state.node_b = spoiler_move.target
            new_state.node_a = duplicator_reply.target
        new_state.spoiler_turn = True
        return new_state

    # ------------------------------------------------------------------
    def as_tuple(self) -> Tuple:
        return (
            self.graph_a.hashable_view(),
            self.graph_b.hashable_view(),
            self.node_a,
            self.node_b,
            self.allow_backward,
            self.allow_jump,
            self.force_same_graph,
        )

    def spoiler_wins(self, spoiler_move: Move) -> bool:
        return not self.legal_responses(spoiler_move)

    def is_terminal(self) -> bool:
        return not self.spoiler_legal_moves()


def play_sequence(position: Position, spoiler_moves: Sequence[Move], duplicator_moves: Sequence[Move]) -> Position:
    state = position
    for sm, dm in zip(spoiler_moves, duplicator_moves):
        state = state.step(sm, dm)
    return state
