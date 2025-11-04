"""Monte-Carlo Tree Search for the Spoiler AI."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..game import Move, Position, RuleSet, legal_responses, spoiler_legal_moves, step
from ..graphs import DiGraph


@dataclass
class MCTSConfig:
    iterations: int = 500
    rollout_depth: int = 8
    exploration_constant: float = math.sqrt(2.0)
    seed: Optional[int] = None


@dataclass
class Node:
    position: Position
    parent: Optional["Node"]
    move: Optional[Move]
    visits: int = 0
    value: float = 0.0
    children: Dict[Move, "Node"] = field(default_factory=dict)
    untried_moves: List[Move] = field(default_factory=list)

    def uct_score(self, c: float) -> float:
        if self.visits == 0:
            return math.inf
        assert self.parent is not None
        return self.value / self.visits + c * math.sqrt(math.log(self.parent.visits + 1) / self.visits)


class MCTSSpoiler:
    def __init__(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        rules: RuleSet,
        config: Optional[MCTSConfig] = None,
    ) -> None:
        self.graph_a = graph_a
        self.graph_b = graph_b
        self.rules = rules
        self.config = config or MCTSConfig()
        self.rng = random.Random(self.config.seed)
        self.visit_heat: Dict[Tuple[str, str], int] = {}

    def _rollout_policy(self, pos: Position) -> float:
        value = 0.0
        for depth in range(self.config.rollout_depth):
            moves = spoiler_legal_moves(self.graph_a, self.graph_b, pos, self.rules)
            if not moves:
                return -1.0
            move = min(
                moves,
                key=lambda mv: len(legal_responses(self.graph_a, self.graph_b, pos, mv, self.rules)) + self.rng.random() * 0.1,
            )
            responses = legal_responses(self.graph_a, self.graph_b, pos, move, self.rules)
            if not responses:
                return 1.0
            reply = self.rng.choice(responses)
            pos = step(self.graph_a, self.graph_b, pos, move, reply)
            value += 1.0 / (1 + len(responses))
        return value / max(1, self.config.rollout_depth)

    def select(self, node: Node) -> Node:
        current = node
        while current.untried_moves == [] and current.children:
            current = max(current.children.values(), key=lambda child: child.uct_score(self.config.exploration_constant))
        return current

    def expand(self, node: Node) -> Node:
        if not node.untried_moves:
            return node
        move = node.untried_moves.pop()
        responses = legal_responses(self.graph_a, self.graph_b, node.position, move, self.rules)
        if not responses:
            child_pos = node.position  # Spoiler wins immediately
        else:
            reply = self.rng.choice(responses)
            child_pos = step(self.graph_a, self.graph_b, node.position, move, reply)
        child = Node(position=child_pos, parent=node, move=move)
        child.untried_moves = spoiler_legal_moves(self.graph_a, self.graph_b, child_pos, self.rules)
        node.children[move] = child
        return child

    def backpropagate(self, node: Node, result: float) -> None:
        current = node
        while current is not None:
            current.visits += 1
            current.value += result
            current = current.parent

    def run(self, root_position: Position) -> Move:
        root = Node(position=root_position, parent=None, move=None)
        root.untried_moves = spoiler_legal_moves(self.graph_a, self.graph_b, root_position, self.rules)
        for _ in range(self.config.iterations):
            node = self.select(root)
            node = self.expand(node)
            result = self._rollout_policy(node.position)
            self.backpropagate(node, result)
        if not root.children:
            raise ValueError("No legal moves for Spoiler")
        best_child = max(root.children.values(), key=lambda child: child.visits)
        self.visit_heat = {
            (child.position.vertex_a, child.position.vertex_b): child.visits
            for child in root.children.values()
        }
        return best_child.move  # type: ignore[return-value]
