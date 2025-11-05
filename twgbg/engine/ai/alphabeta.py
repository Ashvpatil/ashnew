"""Alpha-beta spoiler AI with a battery of classic enhancements."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..game import Move, Position, RuleConfig, legal_responses, spoiler_legal_moves
from ..graphs import DiGraph
from ..utils import Timer
from .dominance import prune_dominated
from .learning import ValueTable, bias_value, load_table
from .symmetry import canonical_label
from .tablebase import get_default_tablebase


@dataclass
class AlphaBetaConfig:
    depth: int = 4
    iter_ms: int = 1000
    weights: Tuple[float, float, float] = (0.6, 1.2, 0.3)
    seed: Optional[int] = None
    collect_pv: bool = True
    table_path: Optional[str] = None


@dataclass
class TTEntry:
    depth: int
    value: float
    best: Move


class AlphaBetaAI:
    """Feature-rich spoiler controller based on alpha-beta search."""

    def __init__(self, config: Optional[AlphaBetaConfig] = None) -> None:
        self.config = config or AlphaBetaConfig()
        self.tt: Dict[str, TTEntry] = {}
        self.tablebase = get_default_tablebase()
        self.value_table: Optional[ValueTable] = (
            load_table(self.config.table_path) if self.config.table_path else None
        )
        self.pv: List[Move] = []

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
        timer = Timer.start_new()
        best_move: Optional[Move] = None
        alpha = -math.inf
        beta = math.inf
        depth_limit = 1
        self.pv = []
        while depth_limit <= self.config.depth:
            value, move, pv = self._search_root(
                graph_a,
                graph_b,
                position,
                config,
                history,
                round_no,
                spoiler_last_side,
                depth_limit,
                alpha,
                beta,
                timer,
            )
            if move is not None:
                best_move = move
                self.pv = pv
            depth_limit += 1
            if timer.elapsed_ms() > self.config.iter_ms:
                break
            alpha = value - 0.5
            beta = value + 0.5
        if best_move is None:
            moves = self._generate_moves(graph_a, graph_b, position, config, spoiler_last_side)
            if not moves:
                raise RuntimeError("No legal spoiler move available")
            best_move = moves[0]
        return best_move

    def _search_root(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        history: Sequence[Move],
        round_no: int,
        spoiler_last_side: Optional[str],
        depth: int,
        alpha: float,
        beta: float,
        timer: Timer,
    ) -> Tuple[float, Optional[Move], List[Move]]:
        best_val = -math.inf
        best_move: Optional[Move] = None
        best_pv: List[Move] = []
        moves = self._generate_moves(graph_a, graph_b, position, config, spoiler_last_side)
        ordered = self._order_moves(graph_a, graph_b, position, config, moves)
        for move in ordered:
            if timer.elapsed_ms() > self.config.iter_ms:
                break
            value = self._spoiler_value(
                graph_a,
                graph_b,
                position,
                config,
                history,
                round_no,
                spoiler_last_side,
                depth,
                alpha,
                beta,
                move,
                timer,
            )
            if value > best_val:
                best_val = value
                best_move = move
                best_pv = [move]
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return best_val, best_move, best_pv

    def _spoiler_value(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        history: Sequence[Move],
        round_no: int,
        spoiler_last_side: Optional[str],
        depth: int,
        alpha: float,
        beta: float,
        move: Move,
        timer: Timer,
    ) -> float:
        responses = self._responses_for_move(graph_a, graph_b, position, move, config)
        if not responses:
            return 1000.0
        value = math.inf
        for reply in responses:
            next_pos = (
                Position(move.dest, reply)
                if move.side == "A"
                else Position(reply, move.dest)
            )
            val = -self._duplicator_value(
                graph_a,
                graph_b,
                next_pos,
                config,
                history,
                round_no + 1,
                move.side,
                depth - 1,
                -beta,
                -alpha,
                timer,
            )
            value = min(value, val)
            if value <= alpha:
                return value
            beta = min(beta, value)
        return value

    def _duplicator_value(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        history: Sequence[Move],
        round_no: int,
        spoiler_last_side: Optional[str],
        depth: int,
        alpha: float,
        beta: float,
        timer: Timer,
    ) -> float:
        if depth < 0 or timer.elapsed_ms() > self.config.iter_ms:
            return self._evaluate(graph_a, graph_b, position, config)

        key = canonical_label(graph_a, graph_b, position.A_curr, position.B_curr)
        tt_entry = self.tt.get(key)
        if tt_entry and tt_entry.depth >= depth:
            return tt_entry.value

        tb = self.tablebase.probe(graph_a, graph_b, position, config)
        if tb == "W":
            return 900.0
        if tb == "L":
            return -900.0

        moves = self._generate_moves(graph_a, graph_b, position, config, spoiler_last_side)
        if not moves:
            return -800.0
        ordered = self._order_moves(graph_a, graph_b, position, config, moves)
        value = -math.inf
        for move in ordered:
            val = self._spoiler_value(
                graph_a,
                graph_b,
                position,
                config,
                history,
                round_no,
                spoiler_last_side,
                depth,
                alpha,
                beta,
                move,
                timer,
            )
            value = max(value, val)
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        self.tt[key] = TTEntry(depth, value, ordered[0] if ordered else moves[0])
        return value

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
            legal = spoiler_legal_moves(
                graph,
                current,
                allow_backward=config.allow_backward,
                allow_jump=config.allow_jump,
            )
            for m in legal:
                moves.append(Move(side, m.mtype, m.dest))
        return moves

    def _order_moves(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
        moves: List[Move],
    ) -> List[Move]:
        if not moves:
            return []
        replies = [
            len(self._responses_for_move(graph_a, graph_b, position, move, config))
            for move in moves
        ]
        filtered = prune_dominated(moves, replies)
        enriched = list(zip(filtered, replies))
        enriched.sort(key=lambda x: (x[1], 0 if x[0].mtype != "jump" else 1))
        return [m for m, _ in enriched]

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
        return legal_responses(other_graph, other_curr, move.mtype)

    def _evaluate(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
        config: RuleConfig,
    ) -> float:
        w_mob, w_pressure, w_asym = self.config.weights
        moves_a = spoiler_legal_moves(graph_a, position.A_curr, config.allow_backward, config.allow_jump)
        moves_b = spoiler_legal_moves(graph_b, position.B_curr, config.allow_backward, config.allow_jump)
        mobility = len(moves_a) + len(moves_b)
        pressure = 0
        for move in moves_a:
            pressure += len(legal_responses(graph_b, position.B_curr, move.mtype))
        for move in moves_b:
            pressure += len(legal_responses(graph_a, position.A_curr, move.mtype))
        asym = abs(len(graph_a.succ.get(position.A_curr or "", [])) - len(graph_b.succ.get(position.B_curr or "", [])))
        value = w_mob * mobility - w_pressure * pressure + w_asym * asym
        if self.value_table is not None:
            value += bias_value(self.value_table, graph_a, graph_b, position.A_curr, position.B_curr)
        return value
