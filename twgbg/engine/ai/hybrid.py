"""Hybrid Spoiler AI combining MCTS guidance with alpha-beta search."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..game import Move, Position, RuleSet
from ..graphs import DiGraph
from .alphabeta import AlphaBetaSpoiler, SearchConfig
from .mcts import MCTSConfig, MCTSSpoiler


@dataclass
class HybridConfig:
    alphabeta_depth: int = 4
    alphabeta_time_ms: int = 2500
    mcts_rollouts: int = 400
    mcts_playout_depth: int = 8
    c_puct: float = 1.2
    top_k: int = 5


@dataclass
class HybridResult:
    best_move: Move
    value: float
    pv: list
    heat: Dict[str, Dict[str, int]]


class HybridSpoiler:
    def __init__(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        rules: RuleSet,
        *,
        config: Optional[HybridConfig] = None,
    ) -> None:
        self.graph_a = graph_a
        self.graph_b = graph_b
        self.rules = rules
        self.config = config or HybridConfig()

    def choose(self, position: Position) -> HybridResult:
        mcts = MCTSSpoiler(
            self.graph_a,
            self.graph_b,
            self.rules,
            config=MCTSConfig(
                rollouts=self.config.mcts_rollouts,
                playout_depth=self.config.mcts_playout_depth,
                c_puct=self.config.c_puct,
            ),
        )
        mcts_result = mcts.run(position)
        guide_scores: Dict[Move, float] = {}
        for move in mcts_result.principal_variation[: self.config.top_k]:
            guide_scores[move] = guide_scores.get(move, 0.0) + 1.0
        alphabeta = AlphaBetaSpoiler(
            self.graph_a,
            self.graph_b,
            self.rules,
            config=SearchConfig(
                depth=self.config.alphabeta_depth,
                time_budget_ms=self.config.alphabeta_time_ms,
                iterative_deepening=True,
            ),
        )
        alphabeta.set_move_hint(guide_scores)
        ab_result = alphabeta.search(position)
        if ab_result.best_move is None:
            raise RuntimeError("Hybrid search failed to find a move")
        return HybridResult(
            best_move=ab_result.best_move,
            value=ab_result.value,
            pv=ab_result.principal_variation,
            heat=mcts_result.visit_heat,
        )
