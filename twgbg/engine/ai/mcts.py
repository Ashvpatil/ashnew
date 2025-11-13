"""Monte Carlo Tree Search spoiler AI."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..game import Move, Position, RuleConfig, legal_responses, spoiler_legal_moves
from ..graphs import DiGraph
from ..utils import DeterministicRNG


@dataclass
class MCTSConfig:
    rollouts: int = 500
    playout_depth: int = 32
    c_puct: float = 1.414
    epsilon: float = 0.1
    seed: Optional[int] = None


@dataclass
class Node:
    value: float = 0.0
    visits: int = 0
    children: Dict[Move, "Node"] = None

    def __post_init__(self) -> None:
        if self.children is None:
            self.children = {}


class MCTSAI:
    """UCT based spoiler search."""

    def __init__(self, config: Optional[MCTSConfig] = None) -> None:
        self.config = config or MCTSConfig()
        self.rng = DeterministicRNG(self.config.seed)
        self.visit_counts: Dict[Tuple[str, str], int] = {}

    def select_move(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        history: Sequence[Move],
        round_no: int,
        spoiler_last_side: Optional[str],
    ) -> Move:
        root = Node()
        legal_moves = self._generate_moves(graph_a, graph_b, position, config, spoiler_last_side)
        if not legal_moves:
            raise RuntimeError("No legal spoiler move available")
        for move in legal_moves:
            root.children[move] = Node()
        for _ in range(self.config.rollouts):
            self._simulate(graph_a, graph_b, position, config, spoiler_last_side, root)
        best_move = max(root.children.items(), key=lambda kv: kv[1].visits)[0]
        return best_move

    def _simulate(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        spoiler_last_side: Optional[str],
        root: Node,
    ) -> None:
        node = root
        pos = position
        side = spoiler_last_side
        path: List[Tuple[Node, Move]] = []
        # Selection
        while node.children:
            move = self._select_child(node)
            path.append((node, move))
            responses = self._responses_for_move(graph_a, graph_b, pos, move, config)
            if not responses:
                self._backprop(path, 1.0)
                return
            reply = self.rng.choice(responses)
            pos = Position(move.dest, reply) if move.side == "A" else Position(reply, move.dest)
            side = move.side
            node = node.children[move]
        # Expansion
        moves = self._generate_moves(graph_a, graph_b, pos, config, side)
        for mv in moves:
            node.children[mv] = Node()
        reward = self._rollout(graph_a, graph_b, pos, config, side)
        self._backprop(path, reward)

    def _select_child(self, node: Node) -> Move:
        total = sum(child.visits for child in node.children.values()) + 1
        best_score = -math.inf
        best_move = next(iter(node.children))
        for move, child in node.children.items():
            if child.visits == 0:
                return move
            exploit = child.value / child.visits
            explore = math.sqrt(math.log(total) / child.visits)
            score = exploit + self.config.c_puct * explore
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    def _backprop(self, path: List[Tuple[Node, Move]], reward: float) -> None:
        for node, move in reversed(path):
            child = node.children[move]
            child.visits += 1
            child.value += reward
            key = (move.side, move.dest or "")
            self.visit_counts[key] = self.visit_counts.get(key, 0) + 1

    def _rollout(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        spoiler_last_side: Optional[str],
    ) -> float:
        pos = position
        side = spoiler_last_side
        for _ in range(self.config.playout_depth):
            moves = self._generate_moves(graph_a, graph_b, pos, config, side)
            if not moves:
                return -1.0
            move = self._epsilon_choice(moves, graph_a, graph_b, pos, config)
            responses = self._responses_for_move(graph_a, graph_b, pos, move, config)
            if not responses:
                return 1.0
            reply = self.rng.choice(responses)
            pos = Position(move.dest, reply) if move.side == "A" else Position(reply, move.dest)
            side = move.side
        return 0.0

    def _epsilon_choice(
        self,
        moves: List[Move],
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
    ) -> Move:
        if self.rng.random() < self.config.epsilon:
            return self.rng.choice(moves)
        best_move = moves[0]
        best_score = math.inf
        for move in moves:
            replies = len(self._responses_for_move(graph_a, graph_b, position, move, config))
            noise = self.rng.random() * 0.01
            score = replies + noise
            if score < best_score:
                best_score = score
                best_move = move
        return best_move

    def _generate_moves(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        spoiler_last_side: Optional[str],
    ) -> List[Move]:
        moves: List[Move] = []
        sides = ["A", "B"]
        if config.force_same_graph in {"A", "B"}:
            sides = [config.force_same_graph]
        if config.mirror_mode and spoiler_last_side:
            sides = ["B" if spoiler_last_side == "A" else "A"]
        for side in sides:
            graph = graph_a if side == "A" else graph_b
            current = position.A_curr if side == "A" else position.B_curr
            legal = spoiler_legal_moves(graph, current, config.allow_backward, config.allow_jump)
            for m in legal:
                moves.append(Move(side, m.mtype, m.dest))
        return moves

    def _responses_for_move(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        move: Move,
        config: RuleConfig,
    ) -> List[str]:
        other_graph = graph_b if move.side == "A" else graph_a
        other_curr = position.B_curr if move.side == "A" else position.A_curr
        responses = legal_responses(other_graph, other_curr, move.mtype)
        return responses
