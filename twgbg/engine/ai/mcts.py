"""Monte Carlo Tree Search Spoiler AI."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..game import Move, Position, RuleSet, legal_responses, spoiler_legal_moves, step
from ..graphs import DiGraph


@dataclass
class MCTSConfig:
    rollouts: int = 800
    playout_depth: int = 10
    c_puct: float = math.sqrt(2.0)
    bias: float = 0.15
    seed: Optional[int] = None


@dataclass
class Node:
    position: Position
    parent: Optional["Node"]
    move: Optional[Move]
    visits: int = 0
    value: float = 0.0
    children: Dict[str, "Node"] = field(default_factory=dict)
    untried: List[Move] = field(default_factory=list)
    terminal: bool = False

    def key_for(self, move: Move) -> str:
        return f"{move.graph}:{move.move_type}:{move.source}->{move.target}"


@dataclass
class MCTSResult:
    best_move: Move
    principal_variation: List[Move]
    visit_heat: Dict[str, Dict[str, int]]


class MCTSSpoiler:
    def __init__(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        rules: RuleSet,
        *,
        config: Optional[MCTSConfig] = None,
    ) -> None:
        self.graph_a = graph_a
        self.graph_b = graph_b
        self.rules = rules
        self.config = config or MCTSConfig()
        self.rng = random.Random(self.config.seed)
        self.visit_heat: Dict[str, Dict[str, int]] = {"A": {}, "B": {}}

    # ------------------------------------------------------------------
    def run(self, root_position: Position) -> MCTSResult:
        root = Node(
            position=root_position,
            parent=None,
            move=None,
            untried=spoiler_legal_moves(self.graph_a, self.graph_b, root_position, self.rules),
        )
        for _ in range(self.config.rollouts):
            node = self._select(root)
            child = self._expand(node)
            reward = self._rollout(child)
            self._backpropagate(child, reward)

        if not root.children:
            raise RuntimeError("Spoiler has no legal moves")

        best_child = max(root.children.values(), key=lambda n: n.visits)
        self._build_heatmap(root)
        pv = self._extract_pv(best_child)
        return MCTSResult(best_child.move, pv, self.visit_heat)

    # ------------------------------------------------------------------
    def _select(self, node: Node) -> Node:
        current = node
        while current.untried == [] and current.children:
            current = max(
                current.children.values(),
                key=lambda child: self._puct(current, child),
            )
        return current

    def _expand(self, node: Node) -> Node:
        if node.terminal:
            return node
        if node.untried:
            move = node.untried.pop()
        else:
            return node
        replies = legal_responses(self.graph_a, self.graph_b, node.position, move, self.rules)
        if not replies:
            # Spoiler wins immediately
            child_position, alive, info = step(
                self.graph_a, self.graph_b, node.position, move, None, self.rules
            )
            child = Node(position=child_position, parent=node, move=move, terminal=True)
            node.children[node.key_for(move)] = child
            return child
        reply = self._choose_reply(node.position, move, replies)
        child_position, alive, info = step(
            self.graph_a, self.graph_b, node.position, move, reply, self.rules
        )
        terminal = not alive
        child = Node(
            position=child_position,
            parent=node,
            move=move,
            terminal=terminal,
            untried=[] if terminal else spoiler_legal_moves(
                self.graph_a, self.graph_b, child_position, self.rules
            ),
        )
        node.children[node.key_for(move)] = child
        return child

    def _rollout(self, node: Node) -> float:
        position = node.position
        total = 0.0
        depth = 0
        alive = not node.terminal
        while depth < self.config.playout_depth and alive:
            moves = spoiler_legal_moves(self.graph_a, self.graph_b, position, self.rules)
            if not moves:
                return 0.0
            move = self._bias_move(position, moves)
            replies = legal_responses(self.graph_a, self.graph_b, position, move, self.rules)
            if not replies:
                return 1.0
            reply = self._choose_reply(position, move, replies)
            position, alive, info = step(
                self.graph_a, self.graph_b, position, move, reply, self.rules
            )
            if not alive:
                return 1.0 if info.get("spoiler_wins") else 0.0
            total += 1.0 / (1 + len(replies))
            depth += 1
        return total / max(1, depth)

    def _backpropagate(self, node: Node, reward: float) -> None:
        current: Optional[Node] = node
        while current is not None:
            current.visits += 1
            current.value += reward
            reward = 1.0 - reward  # alternate perspective for Duplicator
            current = current.parent

    def _puct(self, parent: Node, child: Node) -> float:
        if child.visits == 0:
            return math.inf
        q = child.value / child.visits
        prior = 1.0 / (1 + self._reply_pressure(parent.position, child.move))
        exploration = self.config.c_puct * prior * math.sqrt(parent.visits) / (1 + child.visits)
        return q + exploration

    def _reply_pressure(self, position: Position, move: Move) -> int:
        replies = legal_responses(self.graph_a, self.graph_b, position, move, self.rules)
        return len(replies)

    def _choose_reply(self, position: Position, move: Move, replies: List[Move]) -> Move:
        if len(replies) == 1:
            return replies[0]
        scores: List[Tuple[float, Move]] = []
        for reply in replies:
            graph = self.graph_a if reply.graph == "A" else self.graph_b
            indeg, outdeg = graph.degree(reply.target)
            score = indeg + outdeg + self.config.bias * self.rng.random()
            scores.append((score, reply))
        scores.sort(key=lambda item: item[0], reverse=True)
        # higher degree replies are safer for Duplicator; Spoiler prefers the opposite
        pick_index = int(self.rng.random() * min(3, len(scores)))
        return scores[-(pick_index + 1)][1]

    def _bias_move(self, position: Position, moves: List[Move]) -> Move:
        scored = []
        for move in moves:
            replies = legal_responses(self.graph_a, self.graph_b, position, move, self.rules)
            score = len(replies) + self.config.bias * self.rng.random()
            scored.append((score, move))
        scored.sort(key=lambda item: item[0])
        return scored[0][1]

    def _build_heatmap(self, root: Node) -> None:
        heat_a: Dict[str, int] = {}
        heat_b: Dict[str, int] = {}
        for child in root.children.values():
            move = child.move
            if move is None:
                continue
            if move.graph == "A":
                heat_a[move.target] = heat_a.get(move.target, 0) + child.visits
            else:
                heat_b[move.target] = heat_b.get(move.target, 0) + child.visits
        self.visit_heat = {"A": heat_a, "B": heat_b}

    def _extract_pv(self, node: Node) -> List[Move]:
        sequence: List[Move] = []
        current = node
        while current.move is not None:
            sequence.append(current.move)
            if not current.children:
                break
            current = max(current.children.values(), key=lambda child: child.visits)
        return sequence
