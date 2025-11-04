"""Alpha-beta search implementation for the Spoiler AI."""
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from ..game import (
    MOVE_BACKWARD,
    MOVE_FORWARD,
    MOVE_JUMP,
    Move,
    Position,
    RuleSet,
    decode_position,
    encode_position,
    legal_responses,
    spoiler_legal_moves,
    step,
)
from ..graphs import DiGraph
from .tablebase import Tablebase
from .symmetry import canonical_position


@dataclass
class SearchConfig:
    depth: int = 3
    iterative_deepening: bool = True
    time_budget_ms: int = 2000
    quiescence_threshold: int = 1
    use_symmetry: bool = True


@dataclass
class SearchResult:
    best_move: Optional[Move]
    principal_variation: List[Move]
    value: float
    nodes: int
    duration: float


class HistoryHeuristic:
    def __init__(self) -> None:
        self.table: Dict[Tuple[str, Move], float] = defaultdict(float)

    def update(self, side: str, move: Move, depth: int) -> None:
        self.table[(side, move)] += 2 ** depth

    def score(self, side: str, move: Move) -> float:
        return self.table.get((side, move), 0.0)


class KillerMoves:
    def __init__(self) -> None:
        self.slots: Dict[int, Deque[Move]] = defaultdict(lambda: deque(maxlen=4))

    def add(self, depth: int, move: Move) -> None:
        bucket = self.slots[depth]
        if move not in bucket:
            bucket.appendleft(move)

    def ordering_bonus(self, depth: int, move: Move) -> float:
        bucket = self.slots.get(depth)
        if not bucket:
            return 0.0
        for i, km in enumerate(bucket):
            if km == move:
                return 100.0 / (i + 1)
        return 0.0


class AlphaBetaSpoiler:
    def __init__(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        rules: RuleSet,
        tablebase: Optional[Tablebase] = None,
        config: Optional[SearchConfig] = None,
    ) -> None:
        self.graph_a = graph_a
        self.graph_b = graph_b
        self.rules = rules
        self.tablebase = tablebase or Tablebase()
        self.config = config or SearchConfig()
        self.transposition: Dict[Tuple[str, str, int], Tuple[float, Optional[Move]]] = {}
        self.history = HistoryHeuristic()
        self.killers = KillerMoves()
        self.nodes = 0
        self.pv: List[Move] = []

    def evaluate(self, pos: Position) -> float:
        # Mobility heuristic: fewer responses for Duplicator is better for Spoiler
        moves_a = spoiler_legal_moves(self.graph_a, self.graph_b, pos, self.rules)
        mobility = len(moves_a)
        pressure = 0
        for move in moves_a:
            pressure += len(legal_responses(self.graph_a, self.graph_b, pos, move, self.rules))
        pressure = pressure / max(1, mobility)
        asymmetry = abs(len(self.graph_a.vertices()) - len(self.graph_b.vertices()))
        # Weighting constants determined empirically
        return 0.3 * mobility - 0.7 * pressure + 0.1 * asymmetry

    def _order_moves(self, pos: Position, moves: List[Move], depth: int) -> List[Move]:
        def score(move: Move) -> float:
            history = self.history.score("S", move)
            killer = self.killers.ordering_bonus(depth, move)
            terminal = 1000.0 if legal_responses(self.graph_a, self.graph_b, pos, move, self.rules) == [] else 0.0
            pv_bonus = 50.0 if self.pv and move == self.pv[0] else 0.0
            return history + killer + terminal + pv_bonus

        return sorted(moves, key=score, reverse=True)

    def search(self, pos: Position) -> SearchResult:
        start_time = time.perf_counter()
        self.nodes = 0
        self.pv = []
        best_move: Optional[Move] = None
        best_value = -math.inf
        principal_variation: List[Move] = []

        def time_remaining() -> bool:
            if not self.config.iterative_deepening:
                return True
            return (time.perf_counter() - start_time) * 1000 < self.config.time_budget_ms

        max_depth = self.config.depth
        for depth in range(1, max_depth + 1):
            if not time_remaining():
                break
            value, move, pv = self._alphabeta(pos, depth, -math.inf, math.inf, True, start_time)
            if move is not None:
                best_move = move
                best_value = value
                principal_variation = pv
            if abs(best_value) > 1e6:
                break
        duration = time.perf_counter() - start_time
        return SearchResult(best_move, principal_variation, best_value, self.nodes, duration)

    # ------------------------------------------------------------------
    def _alphabeta(
        self,
        pos: Position,
        depth: int,
        alpha: float,
        beta: float,
        spoiler_turn: bool,
        start_time: float,
        quiescence: bool = False,
    ) -> Tuple[float, Optional[Move], List[Move]]:
        self.nodes += 1
        if self.config.iterative_deepening and (time.perf_counter() - start_time) * 1000 >= self.config.time_budget_ms:
            raise TimeoutError

        table_key = (encode_position(pos), depth, 1 if spoiler_turn else 0)
        if self.config.use_symmetry:
            canon = canonical_position(self.graph_a, self.graph_b, pos)
            table_key = (canon, depth, 1 if spoiler_turn else 0)
        else:
            table_key = (encode_position(pos), depth, 1 if spoiler_turn else 0)
        if table_key in self.transposition:
            value, stored_move = self.transposition[table_key]
            if stored_move is not None:
                return value, stored_move, [stored_move]

        if depth == 0:
            if not quiescence and spoiler_turn:
                return self._quiescence(pos, alpha, beta, start_time)
            return self.evaluate(pos), None, []

        moves = spoiler_legal_moves(self.graph_a, self.graph_b, pos, self.rules)
        if not moves:
            return -1e9, None, []  # Spoiler loses
        moves = self._order_moves(pos, moves, depth)
        best_value = -math.inf
        best_move: Optional[Move] = None
        best_pv: List[Move] = []

        for move in moves:
            responses = legal_responses(self.graph_a, self.graph_b, pos, move, self.rules)
            if not responses:
                value = 1e9 - (self.config.depth - depth)
                if value > best_value:
                    best_value, best_move = value, move
                    best_pv = [move]
                self.history.update("S", move, depth)
                self.killers.add(depth, move)
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
                continue
            worst_for_dup = math.inf
            worst_response: Optional[Move] = None
            for reply in responses:
                new_pos = step(self.graph_a, self.graph_b, pos, move, reply)
                value, _, child_pv = self._alphabeta(new_pos, depth - 1, alpha, beta, True, start_time)
                if value < worst_for_dup:
                    worst_for_dup = value
                    worst_response = reply
                if worst_for_dup <= alpha:
                    break
                beta = min(beta, worst_for_dup)
            value = worst_for_dup
            if value > best_value:
                best_value = value
                best_move = move
                best_pv = [move]
                if worst_response:
                    best_pv.append(worst_response)
                    best_pv.extend(child_pv)
            alpha = max(alpha, best_value)
            if alpha >= beta:
                self.killers.add(depth, move)
                break
        if best_move is not None:
            self.transposition[table_key] = (best_value, best_move)
        return best_value, best_move, best_pv

    def _quiescence(
        self,
        pos: Position,
        alpha: float,
        beta: float,
        start_time: float,
    ) -> Tuple[float, Optional[Move], List[Move]]:
        responses_total = 0
        moves = spoiler_legal_moves(self.graph_a, self.graph_b, pos, self.rules)
        urgent_moves = [m for m in moves if len(legal_responses(self.graph_a, self.graph_b, pos, m, self.rules)) <= self.config.quiescence_threshold]
        stand_pat = self.evaluate(pos)
        if stand_pat >= beta:
            return stand_pat, None, []
        alpha = max(alpha, stand_pat)
        best_value = stand_pat
        best_move: Optional[Move] = None
        for move in urgent_moves:
            responses = legal_responses(self.graph_a, self.graph_b, pos, move, self.rules)
            if not responses:
                return 1e9, move, [move]
            worst_for_dup = math.inf
            for reply in responses:
                new_pos = step(self.graph_a, self.graph_b, pos, move, reply)
                value, _, _ = self._alphabeta(new_pos, 0, alpha, beta, True, start_time, quiescence=True)
                worst_for_dup = min(worst_for_dup, value)
                beta = min(beta, worst_for_dup)
                if beta <= alpha:
                    break
            if worst_for_dup > best_value:
                best_value = worst_for_dup
                best_move = move
            alpha = max(alpha, best_value)
            if alpha >= beta:
                break
        return best_value, best_move, [best_move] if best_move else []
