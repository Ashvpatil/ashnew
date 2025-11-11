"""Iterative deepening alpha-beta search for Spoiler."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..game import JumpWindow, Move, Position, RuleConfig, legal_responses, spoiler_legal_moves, step
from ..graphs import DiGraph
from ..utils import RNG, Timer
from .dominance import filter_dominated
from .learning import LearnedBias
from .symmetry import canonical_position_key
from .tablebase import Tablebase


@dataclass
class SearchStats:
    nodes: int = 0
    cutoffs: int = 0
    qnodes: int = 0
    table_hits: int = 0
    duration_ms: float = 0.0


@dataclass
class SearchResult:
    move: Optional[Move]
    value: float
    depth: int
    pv: List[Move] = field(default_factory=list)
    stats: SearchStats = field(default_factory=SearchStats)


@dataclass
class TTEntry:
    depth: int
    value: float
    flag: str  # "exact"/"lower"/"upper"
    best: Optional[Move]


class SearchTimeout(Exception):
    pass


class AlphaBetaEngine:
    def __init__(self, *, tablebase: Optional[Tablebase] = None, learned_bias: Optional[LearnedBias] = None) -> None:
        self.tablebase = tablebase or Tablebase()
        self.learned_bias = learned_bias or LearnedBias()
        self.tt: Dict[Tuple, TTEntry] = {}
        self.killer_moves: Dict[int, List[Move]] = {}
        self.history_heuristic: Dict[Tuple[str, str, str], float] = {}
        self.stats = SearchStats()
        self.timer = Timer()
        self.time_limit_ms: Optional[int] = None
        self.pv: List[Move] = []

    # ------------------------------------------------------------------
    def evaluate(self, graph_a: DiGraph, graph_b: DiGraph, pos: Position, config: RuleConfig) -> float:
        succ_a = len(graph_a.successors(pos.A_curr))
        succ_b = len(graph_b.successors(pos.B_curr))
        pred_a = len(graph_a.predecessors(pos.A_curr))
        pred_b = len(graph_b.predecessors(pos.B_curr))
        mobility = succ_a + succ_b
        reply_pressure = abs(succ_a - succ_b) + abs(pred_a - pred_b)
        deg_gap = abs((succ_a + pred_a) - (succ_b + pred_b))
        score = 0.6 * mobility - 0.8 * reply_pressure - 0.3 * deg_gap
        score += self.learned_bias.value(pos, graph_a, graph_b, config)
        return score

    # ------------------------------------------------------------------
    def search(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        *,
        config: RuleConfig,
        jump_window: Optional[JumpWindow],
        max_depth: int = 4,
        time_limit_ms: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> SearchResult:
        self.stats = SearchStats()
        self.tt.clear()
        self.killer_moves.clear()
        self.history_heuristic.clear()
        self.pv = []
        self.timer.reset()
        self.time_limit_ms = time_limit_ms
        rng = RNG(seed or config.seed)
        best_result = SearchResult(move=None, value=-math.inf, depth=0, pv=[])
        aspiration = 0.0
        try:
            for depth in range(1, max_depth + 1):
                alpha = aspiration - 100.0
                beta = aspiration + 100.0
                while True:
                    jw = None if jump_window is None else JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
                    try:
                        value, move, pv = self._alphabeta(
                            graph_a,
                            graph_b,
                            pos,
                            depth=depth,
                            alpha=alpha,
                            beta=beta,
                            config=config,
                            round_number=0,
                            jump_window=jw,
                            rng=rng,
                        )
                    except SearchTimeout:
                        raise
                    if value <= alpha:
                        alpha -= 100.0
                        continue
                    if value >= beta:
                        beta += 100.0
                        continue
                    aspiration = value
                    break
                if move is not None:
                    best_result = SearchResult(move=move, value=value, depth=depth, pv=pv, stats=self.stats)
                    self.pv = pv
                if self.time_limit_ms is not None and self.timer.elapsed_ms() > self.time_limit_ms:
                    break
        except SearchTimeout:
            pass
        best_result.stats.duration_ms = self.timer.elapsed_ms()
        return best_result

    # ------------------------------------------------------------------
    def _alphabeta(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        *,
        depth: int,
        alpha: float,
        beta: float,
        config: RuleConfig,
        round_number: int,
        jump_window: Optional[JumpWindow],
        rng: RNG,
    ) -> Tuple[float, Optional[Move], List[Move]]:
        if self.time_limit_ms is not None and self.timer.elapsed_ms() > self.time_limit_ms:
            raise SearchTimeout()
        self.stats.nodes += 1

        tb = self.tablebase.probe(graph_a, graph_b, pos, config=config, round_number=round_number)
        if tb is not None:
            self.stats.table_hits += 1
            return tb, None, []

        key = (canonical_position_key(pos, graph_a, graph_b), depth, round_number, config.key())
        if key in self.tt and self.tt[key].depth >= depth:
            entry = self.tt[key]
            if entry.flag == "exact":
                return entry.value, entry.best, [entry.best] if entry.best else []
            if entry.flag == "lower":
                alpha = max(alpha, entry.value)
            elif entry.flag == "upper":
                beta = min(beta, entry.value)
            if alpha >= beta:
                return entry.value, entry.best, [entry.best] if entry.best else []

        if depth == 0:
            value = self._quiescence(graph_a, graph_b, pos, alpha, beta, config, jump_window, round_number, 0)
            return value, None, []

        moves = spoiler_legal_moves(graph_a, graph_b, pos, config, jump_window, round_number)
        moves = filter_dominated(graph_a, graph_b, pos, moves, config)
        if not moves:
            return -math.inf, None, []

        ordered = self._order_moves(moves, depth, graph_a, graph_b, pos, config)
        best_value = -math.inf
        best_move: Optional[Move] = None
        best_pv: List[Move] = []
        alpha_orig, beta_orig = alpha, beta
        for move in ordered:
            target_graph = graph_b if move.side == "A" else graph_a
            replies = legal_responses(target_graph, pos, move, config)
            if not replies:
                self._update_history(depth, move)
                return float("inf"), move, [move]
            move_value = math.inf
            chosen_child_pv: List[Move] = []
            for reply in replies:
                jw = None if jump_window is None else JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
                new_pos, alive, info = step(
                    graph_a,
                    graph_b,
                    pos,
                    move,
                    reply,
                    config=config,
                    jump_window=jw,
                    round_number=round_number,
                )
                if "Spoiler wins" in info:
                    return float("inf"), move, [move]
                if not alive:
                    move_value = min(move_value, -math.inf)
                    continue
                child_value, _, child_pv = self._alphabeta(
                    graph_a,
                    graph_b,
                    new_pos,
                    depth=depth - 1,
                    alpha=-beta,
                    beta=-alpha,
                    config=config,
                    round_number=round_number + 1,
                    jump_window=jw,
                    rng=rng,
                )
                child_value = -child_value
                if child_value < move_value:
                    move_value = child_value
                    chosen_child_pv = child_pv
                if move_value <= alpha:
                    break
            if move_value > best_value:
                best_value = move_value
                best_move = move
                best_pv = [move] + chosen_child_pv
            alpha = max(alpha, best_value)
            if alpha >= beta:
                self.stats.cutoffs += 1
                self._store_killer(depth, move)
                break
        flag = "exact"
        if best_value <= alpha_orig:
            flag = "upper"
        elif best_value >= beta_orig:
            flag = "lower"
        self.tt[key] = TTEntry(depth=depth, value=best_value, flag=flag, best=best_move)
        return best_value, best_move, best_pv

    def _order_moves(self, moves: List[Move], depth: int, graph_a: DiGraph, graph_b: DiGraph, pos: Position, config: RuleConfig) -> List[Move]:
        scored = []
        for mv in moves:
            target_graph = graph_b if mv.side == "A" else graph_a
            replies = legal_responses(target_graph, pos, mv, config)
            reply_count = len(replies)
            terminal_bonus = 1000 if reply_count == 0 else 0
            killer_bonus = 50 if mv in self.killer_moves.get(depth, []) else 0
            history_bonus = self.history_heuristic.get((mv.side, mv.mtype, mv.dest), 0.0)
            pv_bonus = 150 if self.pv and depth <= len(self.pv) and self.pv[depth - 1] == mv else 0
            score = terminal_bonus + killer_bonus + history_bonus + pv_bonus - reply_count * 5
            scored.append((score, -reply_count, mv.dest, mv))
        scored.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
        return [entry[3] for entry in scored]

    def _quiescence(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        alpha: float,
        beta: float,
        config: RuleConfig,
        jump_window: Optional[JumpWindow],
        round_number: int,
        depth: int,
    ) -> float:
        self.stats.qnodes += 1
        stand_pat = self.evaluate(graph_a, graph_b, pos, config)
        if stand_pat >= beta:
            return beta
        alpha = max(alpha, stand_pat)
        if depth >= 6:
            return stand_pat
        moves = spoiler_legal_moves(graph_a, graph_b, pos, config, jump_window, round_number)
        urgent = [mv for mv in moves if len(legal_responses(graph_b if mv.side == "A" else graph_a, pos, mv, config)) <= 1]
        for move in urgent:
            target_graph = graph_b if move.side == "A" else graph_a
            replies = legal_responses(target_graph, pos, move, config)
            if not replies:
                return float("inf")
            for reply in replies:
                jw = None if jump_window is None else JumpWindow(history=list(jump_window.history), limit=jump_window.limit)
                new_pos, alive, info = step(
                    graph_a,
                    graph_b,
                    pos,
                    move,
                    reply,
                    config=config,
                    jump_window=jw,
                    round_number=round_number,
                )
                if "Spoiler wins" in info:
                    return float("inf")
                if not alive:
                    continue
                score = -self._quiescence(graph_a, graph_b, new_pos, -beta, -alpha, config, jw, round_number + 1, depth + 1)
                if score >= beta:
                    return beta
                alpha = max(alpha, score)
        return alpha

    def _store_killer(self, depth: int, move: Move) -> None:
        killers = self.killer_moves.setdefault(depth, [])
        if move not in killers:
            killers.insert(0, move)
        del killers[2:]

    def _update_history(self, depth: int, move: Move) -> None:
        key = (move.side, move.mtype, move.dest)
        self.history_heuristic[key] = self.history_heuristic.get(key, 0.0) + depth * depth


__all__ = ["AlphaBetaEngine", "SearchResult", "SearchStats"]
