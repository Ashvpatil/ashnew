"""Hybrid controller that combines MCTS and alpha-beta search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..game import Move, Position, RuleConfig
from ..graphs import DiGraph
from .alphabeta import AlphaBetaAI, AlphaBetaConfig
from .mcts import MCTSAI, MCTSConfig


@dataclass
class HybridConfig:
    switch_branching: int = 6
    mcts_rollouts: int = 300
    ab_depth: int = 4
    iter_ms: int = 800


class HybridAI:
    """Controller that runs a short MCTS to seed alpha-beta ordering and vice-versa."""

    def __init__(self, config: Optional[HybridConfig] = None) -> None:
        self.config = config or HybridConfig()
        self.alphabeta = AlphaBetaAI(AlphaBetaConfig(depth=self.config.ab_depth, iter_ms=self.config.iter_ms))
        self.mcts = MCTSAI(MCTSConfig(rollouts=self.config.mcts_rollouts))

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
        moves = self.alphabeta._generate_moves(graph_a, graph_b, position, config, spoiler_last_side)
        if len(moves) >= self.config.switch_branching:
            move = self.mcts.select_move(graph_a, graph_b, position, config, history, round_no, spoiler_last_side)
        else:
            move = self.alphabeta.select_move(graph_a, graph_b, position, config, history, round_no, spoiler_last_side)
        return move
