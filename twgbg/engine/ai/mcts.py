"""Monte-Carlo Tree Search for Spoiler."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..game import JumpWindow, Move, Position, RuleConfig, legal_responses, spoiler_legal_moves, step
from ..graphs import DiGraph
from ..utils import RNG


@dataclass
class NodeStats:
    visits: int = 0
    value: float = 0.0
    children: Dict[Move, "NodeStats"] = field(default_factory=dict)

    def uct(self, parent_visits: int, c_puct: float) -> float:
        if self.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        exploration = c_puct * math.sqrt(math.log(parent_visits) / self.visits)
        return exploitation + exploration


class MCTSEngine:
    def __init__(
        self,
        *,
        c_puct: float = 1.414,
        rollout_depth: int = 24,
        epsilon: float = 0.15,
    ) -> None:
        self.c_puct = c_puct
        self.rollout_depth = rollout_depth
        self.epsilon = epsilon
        self.root = NodeStats()
        self.visit_counts: Dict[Tuple[str, str], int] = {}

    def search(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        *,
        config: RuleConfig,
        jump_window: Optional[JumpWindow],
        iterations: int = 800,
        seed: Optional[int] = None,
    ) -> Move:
        rng = RNG(seed or config.seed)
        self.root = NodeStats()
        self.visit_counts.clear()
        for _ in range(iterations):
            jw = None if jump_window is None else JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
            self._iterate(graph_a, graph_b, pos, config, jw, rng)
        if not self.root.children:
            raise RuntimeError("MCTS produced no children")
        return max(self.root.children.items(), key=lambda item: item[1].visits)[0]

    def _iterate(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        config: RuleConfig,
        jump_window: Optional[JumpWindow],
        rng: RNG,
    ) -> None:
        node = self.root
        state = pos
        depth = 0
        path: List[Tuple[NodeStats, Move]] = []
        round_number = 0
        maximizing = True
        while True:
            moves = spoiler_legal_moves(graph_a, graph_b, state, config, jump_window, round_number)
            if not moves:
                reward = -1.0 if maximizing else 1.0
                self._backprop(path, reward)
                return
            if node.children:
                total = sum(child.visits for child in node.children.values()) + 1
                move = max(node.children.items(), key=lambda item: item[1].uct(total, self.c_puct))[0]
            else:
                for mv in moves:
                    node.children[mv] = NodeStats()
                move = self._select_expand_move(node.children, moves, rng)
            path.append((node, move))
            replies = legal_responses(graph_b if move.side == "A" else graph_a, state, move, config)
            if not replies:
                self._backprop(path, 1.0 if maximizing else -1.0)
                return
            jw = None if jump_window is None else JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
            next_state, alive, info = step(
                graph_a,
                graph_b,
                state,
                move,
                rng.choice(replies),
                config=config,
                jump_window=jw,
                round_number=round_number,
            )
            if "Spoiler wins" in info:
                self._backprop(path, 1.0 if maximizing else -1.0)
                return
            if not alive:
                self._backprop(path, -1.0 if maximizing else 1.0)
                return
            node = node.children[move]
            state = next_state
            jump_window = jw
            maximizing = not maximizing
            round_number += 1
            if node.visits == 0:
                reward = self._rollout(graph_a, graph_b, state, config, jump_window, maximizing, round_number, rng)
                self._backprop(path, reward)
                return

    def _select_expand_move(self, children: Dict[Move, NodeStats], moves: List[Move], rng: RNG) -> Move:
        items = []
        for mv in moves:
            child = children[mv]
            bias = 1.0 / (1 + len(child.children))
            items.append((mv, bias))
        return rng.weighted_choice(items)

    def _rollout(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        config: RuleConfig,
        jump_window: Optional[JumpWindow],
        maximizing: bool,
        round_number: int,
        rng: RNG,
    ) -> float:
        state = pos
        jw = None if jump_window is None else JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
        for depth in range(self.rollout_depth):
            moves = spoiler_legal_moves(graph_a, graph_b, state, config, jw, round_number)
            if not moves:
                return -1.0 if maximizing else 1.0
            if rng.random() < self.epsilon:
                move = rng.choice(moves)
            else:
                scored = []
                for mv in moves:
                    replies = legal_responses(graph_b if mv.side == "A" else graph_a, state, mv, config)
                    scored.append((1 / (1 + len(replies)), mv))
                scored.sort(key=lambda item: item[0], reverse=True)
                move = scored[0][1]
            replies = legal_responses(graph_b if move.side == "A" else graph_a, state, move, config)
            reply = rng.choice(replies) if replies else None
            state, alive, info = step(
                graph_a,
                graph_b,
                state,
                move,
                reply,
                config=config,
                jump_window=jw,
                round_number=round_number,
            )
            if "Spoiler wins" in info:
                return 1.0 if maximizing else -1.0
            if not alive:
                return -1.0 if maximizing else 1.0
            round_number += 1
            maximizing = not maximizing
        return 0.0

    def _backprop(self, path: List[Tuple[NodeStats, Move]], reward: float) -> None:
        for node, move in reversed(path):
            child = node.children[move]
            child.visits += 1
            child.value += reward
            node.visits += 1
            key = (move.side, move.dest)
            self.visit_counts[key] = self.visit_counts.get(key, 0) + 1
            reward = -reward


__all__ = ["MCTSEngine"]
