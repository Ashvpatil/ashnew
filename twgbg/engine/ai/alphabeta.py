"""Advanced alpha-beta Spoiler AI."""
from __future__ import annotations

import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from ..game import (
    MOVE_JUMP,
    Move,
    Position,
    RuleSet,
    encode_position,
    legal_responses,
    spoiler_legal_moves,
    step,
)
from ..graphs import DiGraph
from .dominance import prune_dominated_moves
from .learning import ValueTable
from .symmetry import canonical_position
from .tablebase import Tablebase

INF = 10_000_000.0


@dataclass
class SearchConfig:
    depth: int = 3
    iterative_deepening: bool = True
    time_budget_ms: int = 2000
    quiescence_threshold: int = 1
    allow_quiescence: bool = True
    weights: Tuple[float, float, float] = (0.5, 0.35, 0.15)
    randomness: float = 0.0
    use_symmetry: bool = True
    enable_dominance: bool = True
    enable_tablebase: bool = True


@dataclass
class SearchResult:
    best_move: Optional[Move]
    principal_variation: List[Move]
    value: float
    nodes: int
    duration: float


class HistoryHeuristic:
    def __init__(self) -> None:
        self.table: Dict[Tuple[str, str, str], float] = defaultdict(float)

    def update(self, move: Move, depth: int) -> None:
        key = (move.graph, move.move_type, move.target)
        self.table[key] += 2.0 ** depth

    def score(self, move: Move) -> float:
        key = (move.graph, move.move_type, move.target)
        return self.table.get(key, 0.0)


class KillerMoves:
    def __init__(self, slots: int = 4) -> None:
        self.slots = slots
        self.table: Dict[int, Deque[Move]] = defaultdict(lambda: deque(maxlen=self.slots))

    def add(self, depth: int, move: Move) -> None:
        bucket = self.table[depth]
        if move not in bucket:
            bucket.appendleft(move)

    def score(self, depth: int, move: Move) -> float:
        bucket = self.table.get(depth)
        if not bucket:
            return 0.0
        for idx, stored in enumerate(bucket):
            if stored == move:
                return 100.0 / (idx + 1)
        return 0.0


class AlphaBetaSpoiler:
    """Spoiler AI using alpha-beta search with rich move ordering."""

    def __init__(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        rules: RuleSet,
        *,
        tablebase: Optional[Tablebase] = None,
        value_table: Optional[ValueTable] = None,
        config: Optional[SearchConfig] = None,
    ) -> None:
        self.graph_a = graph_a
        self.graph_b = graph_b
        self.rules = rules
        self.tablebase = tablebase or Tablebase()
        self.value_table = value_table
        self.config = config or SearchConfig()
        self.transposition: Dict[Tuple, Tuple[float, Optional[Move]]] = {}
        self.history = HistoryHeuristic()
        self.killers = KillerMoves()
        self.nodes = 0
        self.pv: List[Move] = []
        self._guide: Dict[Tuple[str, str, str, str], float] = {}
        self._rng = random.Random(0)

    # ------------------------------------------------------------------
    def set_move_hint(self, scores: Dict[Move, float]) -> None:
        """Provide ordering hints from a companion search (hybrid engine)."""

        self._guide = {
            (move.graph, move.move_type, move.source, move.target): score
            for move, score in scores.items()
        }

    # ------------------------------------------------------------------
    def search(self, position: Position) -> SearchResult:
        start = time.perf_counter()
        self.nodes = 0
        self.pv = []
        best_move: Optional[Move] = None
        best_value = -INF
        best_pv: List[Move] = []

        try:
            depths = range(1, self.config.depth + 1)
            if not self.config.iterative_deepening:
                depths = [self.config.depth]
            for depth in depths:
                value, move, pv = self._alphabeta(position, depth, -INF, INF, start)
                if move is not None:
                    best_move, best_value, best_pv = move, value, pv
                if time.perf_counter() - start > self.config.time_budget_ms / 1000:
                    break
                if best_value >= INF / 2:
                    break
        except TimeoutError:
            pass

        duration = time.perf_counter() - start
        self.pv = best_pv
        return SearchResult(best_move, best_pv, best_value, self.nodes, duration)

    # ------------------------------------------------------------------
    def _alphabeta(
        self,
        position: Position,
        depth: int,
        alpha: float,
        beta: float,
        start_time: float,
        quiescence: bool = False,
    ) -> Tuple[float, Optional[Move], List[Move]]:
        self.nodes += 1
        if (
            self.config.iterative_deepening
            and (time.perf_counter() - start_time) * 1000 >= self.config.time_budget_ms
        ):
            raise TimeoutError

        key = self._tt_key(position, depth)
        if key in self.transposition:
            value, stored_move = self.transposition[key]
            if stored_move is not None:
                return value, stored_move, [stored_move]

        if depth == 0:
            if self.config.allow_quiescence and not quiescence:
                return self._quiescence(position, alpha, beta, start_time)
            return self.evaluate(position), None, []

        table_hit = self._probe_tablebase(position)
        if table_hit is not None:
            return (INF if table_hit else -INF), None, []

        moves = spoiler_legal_moves(self.graph_a, self.graph_b, position, self.rules)
        if not moves:
            return -INF, None, []

        if self.config.enable_dominance:
            moves = prune_dominated_moves(self.graph_a, self.graph_b, position, moves, self.rules)

        ordered = self._order_moves(position, moves, depth)
        best_value = -INF
        best_move: Optional[Move] = None
        best_pv: List[Move] = []

        for move in ordered:
            replies = legal_responses(self.graph_a, self.graph_b, position, move, self.rules)
            if not replies:
                value = INF - (self.config.depth - depth)
                if value > best_value:
                    best_value, best_move = value, move
                    best_pv = [move]
                self.history.update(move, depth)
                self.killers.add(depth, move)
                alpha = max(alpha, best_value)
                if alpha >= beta:
                    break
                continue

            worst_value = INF
            best_reply: Optional[Move] = None
            best_reply_position: Optional[Position] = None
            for reply in replies:
                new_pos, alive, info = step(
                    self.graph_a,
                    self.graph_b,
                    position,
                    move,
                    reply,
                    self.rules,
                )
                if not alive:
                    if info.get("spoiler_wins"):
                        child_value = INF - (self.config.depth - depth)
                    else:
                        child_value = -INF + (self.config.depth - depth)
                else:
                    child_value, _, _ = self._alphabeta(
                        new_pos, depth - 1, -beta, -alpha, start_time
                    )
                    child_value = -child_value
                if child_value < worst_value:
                    worst_value = child_value
                    best_reply = reply
                    best_reply_position = new_pos
                beta = min(beta, worst_value)
                if beta <= alpha:
                    break

            if worst_value > best_value:
                best_value = worst_value
                best_move = move
                best_pv = [move]
                if best_reply:
                    best_pv.append(best_reply)
                if best_reply_position is not None:
                    child_key = self._tt_key(best_reply_position, depth - 1)
                    child_entry = self.transposition.get(child_key)
                    if child_entry and child_entry[1] is not None:
                        best_pv.append(child_entry[1])
            alpha = max(alpha, best_value)
            if alpha >= beta:
                self.killers.add(depth, move)
                break

        if best_move is not None:
            self.transposition[key] = (best_value, best_move)
        else:
            self.transposition[key] = (best_value, None)
        return best_value, best_move, best_pv

    # ------------------------------------------------------------------
    def _quiescence(
        self,
        position: Position,
        alpha: float,
        beta: float,
        start_time: float,
    ) -> Tuple[float, Optional[Move], List[Move]]:
        stand_pat = self.evaluate(position)
        if stand_pat >= beta:
            return stand_pat, None, []
        alpha = max(alpha, stand_pat)

        urgent_moves = [
            move
            for move in spoiler_legal_moves(self.graph_a, self.graph_b, position, self.rules)
            if len(legal_responses(self.graph_a, self.graph_b, position, move, self.rules))
            <= self.config.quiescence_threshold
        ]
        best_value = stand_pat
        best_move: Optional[Move] = None
        for move in urgent_moves:
            replies = legal_responses(self.graph_a, self.graph_b, position, move, self.rules)
            if not replies:
                return INF, move, [move]
            worst = INF
            for reply in replies:
                new_pos, alive, info = step(
                    self.graph_a, self.graph_b, position, move, reply, self.rules
                )
                if not alive:
                    child_value = INF if info.get("spoiler_wins") else -INF
                else:
                    child_value, _, _ = self._alphabeta(
                        new_pos, 0, -beta, -alpha, start_time, quiescence=True
                    )
                    child_value = -child_value
                worst = min(worst, child_value)
                beta = min(beta, worst)
                if beta <= alpha:
                    break
            if worst > best_value:
                best_value = worst
                best_move = move
            alpha = max(alpha, best_value)
            if alpha >= beta:
                break
        return best_value, best_move, [best_move] if best_move else []

    # ------------------------------------------------------------------
    def _order_moves(self, position: Position, moves: Sequence[Move], depth: int) -> List[Move]:
        scores: List[Tuple[float, Move]] = []
        for move in moves:
            guide = self._guide.get((move.graph, move.move_type, move.source, move.target), 0.0)
            killer = self.killers.score(depth, move)
            history = self.history.score(move)
            terminal_bonus = 400.0 if not legal_responses(self.graph_a, self.graph_b, position, move, self.rules) else 0.0
            randomness = self.config.randomness * self._rng.random()
            scores.append((guide + killer + history + terminal_bonus + randomness, move))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [move for _, move in scores]

    # ------------------------------------------------------------------
    def evaluate(self, position: Position) -> float:
        moves = spoiler_legal_moves(self.graph_a, self.graph_b, position, self.rules)
        mobility = len(moves)
        reply_count = 0
        urgent = 0
        for move in moves:
            responses = legal_responses(self.graph_a, self.graph_b, position, move, self.rules)
            reply_count += len(responses)
            if len(responses) <= self.config.quiescence_threshold:
                urgent += 1
        avg_replies = reply_count / max(1, mobility)
        indeg_a, outdeg_a = self.graph_a.degree(position.vertex_a)
        indeg_b, outdeg_b = self.graph_b.degree(position.vertex_b)
        asym = abs(indeg_a - indeg_b) + abs(outdeg_a - outdeg_b)
        mobility_term, pressure_term, asym_term = self.config.weights
        value = (
            mobility_term * mobility
            - pressure_term * avg_replies
            + asym_term * asym
            + 0.05 * urgent
        )
        if self.value_table is not None:
            value += 0.1 * self.value_table.lookup(position, indeg_a, outdeg_a)
        return value

    # ------------------------------------------------------------------
    def _tt_key(self, position: Position, depth: int) -> Tuple:
        rule_signature = (
            self.rules.allow_backward,
            self.rules.allow_jump,
            self.rules.force_same_graph,
            self.rules.jump_cooldown,
            self.rules.jump_window,
            self.rules.jump_limit,
            self.rules.round_limit,
            self.rules.mirror_mode,
        )
        if self.config.use_symmetry:
            canonical = canonical_position(self.graph_a, self.graph_b, position)
        else:
            canonical = encode_position(position)
        return canonical, depth, rule_signature

    def _probe_tablebase(self, position: Position) -> Optional[bool]:
        if not self.config.enable_tablebase:
            return None
        return self.tablebase.probe(position)


class AlphaBetaSpoilerIterative(AlphaBetaSpoiler):
    """Convenience wrapper to expose iterative deepening explicitly."""

    def __init__(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        rules: RuleSet,
        *,
        depth: int = 6,
        time_budget_ms: int = 4000,
    ) -> None:
        super().__init__(
            graph_a,
            graph_b,
            rules,
            config=SearchConfig(depth=depth, time_budget_ms=time_budget_ms, iterative_deepening=True),
        )
