"""Alpha-beta Spoiler AI implementation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
import math

from ..engine.game import Move, Position
from ..engine.graphs import DiGraph
from .learning import TabularValue
from .tablebase import Tablebase
from .symmetry import prune_symmetric_moves


Score = float


@dataclass
class SearchInfo:
    best_move: Optional[Move]
    principal_variation: List[Move]
    depth_reached: int
    nodes: int
    value: Score
    duration: float
    alt_moves: List[Tuple[Move, Score]]


@dataclass
class SearchConfig:
    max_depth: int = 4
    iterative: bool = True
    time_budget: float = 2.0
    quiescence_depth: int = 2
    mobility_weight: float = 0.1
    pressure_weight: float = 1.0
    asymmetry_weight: float = 0.3
    use_tablebase: bool = True
    seed: Optional[int] = None


@dataclass
class HistoryHeuristic:
    history: Dict[Tuple[str, str, str], int] = field(default_factory=dict)

    def bump(self, move: Move, depth: int) -> None:
        key = (move.graph, move.source, move.target)
        self.history[key] = self.history.get(key, 0) + 2 ** depth

    def score(self, move: Move) -> int:
        key = (move.graph, move.source, move.target)
        return self.history.get(key, 0)


class AlphaBetaSpoiler:
    """Alpha-beta searcher with a mix of classic heuristics."""

    def __init__(self, config: Optional[SearchConfig] = None, tablebase: Optional[Tablebase] = None, value_fn: Optional[TabularValue] = None) -> None:
        self.config = config or SearchConfig()
        self.tablebase = tablebase or Tablebase()
        self.value_fn = value_fn or TabularValue()
        self.transposition: Dict[Tuple, Tuple[int, Score, Optional[Move]]] = {}
        self.killer_moves: Dict[int, List[Move]] = {}
        self.history = HistoryHeuristic()

    # ------------------------------------------------------------------
    def evaluate(self, position: Position) -> Score:
        """Static evaluation; larger is better for the Spoiler."""

        spoiler_moves = position.spoiler_legal_moves()
        move_count = len(spoiler_moves)
        sig_a = len(position.graph_a.partitions())
        sig_b = len(position.graph_b.partitions())
        asym = abs(sig_a - sig_b)
        table_val = 0.0
        if self.config.use_tablebase:
            tb = self.tablebase.lookup(position)
            if tb is not None:
                return tb
        learned = self.value_fn.get(position)
        pressure = 0.0
        if spoiler_moves:
            first_move = spoiler_moves[0]
            pressure = 1.0 / (1 + len(position.legal_responses(first_move)))
        else:
            pressure = 10.0
        return (
            self.config.pressure_weight * pressure
            + self.config.mobility_weight * move_count
            + self.config.asymmetry_weight * asym
            + learned
            + table_val
        )

    # ------------------------------------------------------------------
    def choose_move(self, position: Position) -> SearchInfo:
        start = time.time()
        best_move: Optional[Move] = None
        principal_variation: List[Move] = []
        best_value = -math.inf
        max_depth = self.config.max_depth
        depth_reached = 0
        nodes = 0
        alt_scores: List[Tuple[Move, Score]] = []
        moves = prune_symmetric_moves(position, position.spoiler_legal_moves())

        if not moves:
            return SearchInfo(None, [], 0, 0, -math.inf, 0.0, [])

        time_limit = start + self.config.time_budget
        for depth in range(1, max_depth + 1):
            current_best = None
            current_value = -math.inf
            current_alt: List[Tuple[Move, Score]] = []
            ordered_moves = self.order_moves(position, moves, depth)
            for move in ordered_moves:
                if time.time() > time_limit:
                    break
                value, pv, visited = self.search(position, move, depth - 1, -math.inf, math.inf)
                nodes += visited
                current_alt.append((move, value))
                if value > current_value:
                    current_best = move
                    current_value = value
                    principal_variation = [move] + pv
            if current_best is not None:
                best_move = current_best
                best_value = current_value
                depth_reached = depth
                alt_scores = sorted(current_alt, key=lambda x: x[1], reverse=True)[:5]
            if not self.config.iterative or time.time() > time_limit:
                break
        duration = time.time() - start
        return SearchInfo(best_move, principal_variation, depth_reached, nodes, best_value, duration, alt_scores)

    # ------------------------------------------------------------------
    def order_moves(self, position: Position, moves: List[Move], depth: int) -> List[Move]:
        scored: List[Tuple[float, Move]] = []
        for move in moves:
            score = 0.0
            if position.spoiler_wins(move):
                score += 1000.0
            score += self.history.score(move)
            killers = self.killer_moves.get(depth, [])
            if move in killers:
                score += 100.0
            score += len(position.legal_responses(move))
            scored.append((score, move))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    # ------------------------------------------------------------------
    def search(self, position: Position, move: Move, depth: int, alpha: float, beta: float) -> Tuple[Score, List[Move], int]:
        key = (position.as_tuple(), move, depth)
        if key in self.transposition:
            stored_depth, value, pv_move = self.transposition[key]
            if stored_depth >= depth:
                return value, [pv_move] if pv_move else [], 1

        nodes = 1
        if position.spoiler_wins(move):
            value = 100.0 + depth
            self.transposition[key] = (depth, value, None)
            return value, [], nodes

        replies = position.legal_responses(move)
        best_value = -math.inf
        best_line: List[Move] = []
        for reply in replies:
            child = position.clone()
            child = child.step(move, reply)
            value = -self.duplicator_value(child, depth - 1, -beta, -alpha)
            nodes += 1
            if value > best_value:
                best_value = value
                best_line = [reply]
                self.history.bump(move, depth + 1)
            alpha = max(alpha, value)
            if alpha >= beta:
                self.record_killer(depth, move)
                break
        self.transposition[key] = (depth, best_value, best_line[0] if best_line else None)
        return best_value, best_line, nodes

    # ------------------------------------------------------------------
    def duplicator_value(self, position: Position, depth: int, alpha: float, beta: float) -> Score:
        if depth < 0:
            return self.quiescence(position, alpha, beta, self.config.quiescence_depth)
        moves = prune_symmetric_moves(position, position.spoiler_legal_moves())
        if not moves:
            return -100.0
        value = math.inf
        for move in self.order_moves(position, moves, depth):
            score, _, _ = self.search(position, move, depth, alpha, beta)
            value = min(value, score)
            beta = min(beta, score)
            if beta <= alpha:
                break
        return value

    def quiescence(self, position: Position, alpha: float, beta: float, depth: int) -> Score:
        stand_pat = self.static_evaluation(position)
        if depth <= 0:
            return stand_pat
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        moves = [m for m in position.spoiler_legal_moves() if len(position.legal_responses(m)) <= 1]
        for move in moves:
            score, _, _ = self.search(position, move, 0, alpha, beta)
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    def static_evaluation(self, position: Position) -> Score:
        moves = len(position.spoiler_legal_moves())
        reply_pressure = 0.0
        for move in position.spoiler_legal_moves():
            replies = len(position.legal_responses(move))
            if replies:
                reply_pressure += 1 / replies
            else:
                reply_pressure += 2.0
        return 0.5 * moves + reply_pressure + self.value_fn.get(position)

    def record_killer(self, depth: int, move: Move) -> None:
        killers = self.killer_moves.setdefault(depth, [])
        if move not in killers:
            killers.append(move)
            if len(killers) > 2:
                killers.pop(0)
