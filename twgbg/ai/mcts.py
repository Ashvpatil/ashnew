"""Monte-Carlo Tree Search Spoiler AI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import random
import time

from ..engine.game import Move, Position
from .symmetry import prune_symmetric_moves
from .learning import TabularValue


@dataclass
class MCTSConfig:
    iterations: int = 1000
    time_budget: float = 2.0
    c_puct: float = 1.414
    rollout_depth: int = 30
    seed: Optional[int] = None


@dataclass
class Node:
    parent: Optional["Node"]
    move: Optional[Move]
    position: Position
    visits: int = 0
    total_value: float = 0.0
    children: Dict[str, "Node"] = field(default_factory=dict)
    untried: List[Move] = field(default_factory=list)

    def uct_score(self, c_puct: float) -> float:
        if self.parent is None or self.visits == 0:
            return math.inf
        exploitation = self.total_value / self.visits
        exploration = c_puct * math.sqrt(math.log(self.parent.visits + 1) / self.visits)
        return exploitation + exploration

    def best_child(self, c_puct: float) -> "Node":
        return max(self.children.values(), key=lambda n: n.uct_score(c_puct))


class MCTSSpoiler:
    def __init__(self, config: Optional[MCTSConfig] = None, value_fn: Optional[TabularValue] = None) -> None:
        self.config = config or MCTSConfig()
        self.rng = random.Random(self.config.seed)
        self.value_fn = value_fn or TabularValue()
        self.visit_heat: Dict[Tuple[str, str], int] = {}

    def choose_move(self, position: Position) -> Tuple[Optional[Move], Dict[Tuple[str, str], int]]:
        root = Node(parent=None, move=None, position=position.clone())
        root.untried = prune_symmetric_moves(position, position.spoiler_legal_moves())
        if not root.untried:
            return None, {}

        start = time.time()
        iterations = 0
        while iterations < self.config.iterations and time.time() - start < self.config.time_budget:
            node = self.select(root)
            value = self.simulate(node.position.clone(), depth=self.config.rollout_depth)
            self.backpropagate(node, value)
            iterations += 1

        best = max(root.children.values(), key=lambda n: n.visits, default=None)
        move = best.move if best else root.untried[0]
        self.visit_heat = {(child.move.graph, child.move.target): child.visits for child in root.children.values() if child.move}
        return move, self.visit_heat

    def select(self, node: Node) -> Node:
        while True:
            if node.untried:
                move = node.untried.pop()
                child_pos = node.position.clone()
                responses = child_pos.legal_responses(move)
                if not responses:
                    new_pos = child_pos
                else:
                    reply = min(responses, key=lambda m: len(child_pos.legal_responses(m)))
                    new_pos = child_pos.step(move, reply)
                child = Node(parent=node, move=move, position=new_pos)
                child.untried = prune_symmetric_moves(new_pos, new_pos.spoiler_legal_moves())
                node.children[move.describe()] = child
                return child
            if not node.children:
                return node
            node = node.best_child(self.config.c_puct)

    def simulate(self, position: Position, depth: int) -> float:
        for _ in range(depth):
            moves = prune_symmetric_moves(position, position.spoiler_legal_moves())
            if not moves:
                return -1.0
            move = min(moves, key=lambda m: len(position.legal_responses(m)))
            replies = position.legal_responses(move)
            if not replies:
                return 1.0
            reply = self.rng.choice(replies)
            position = position.step(move, reply)
        return self.value_fn.get(position)

    def backpropagate(self, node: Node, value: float) -> None:
        while node is not None:
            node.visits += 1
            node.total_value += value
            value = -value
            node = node.parent
