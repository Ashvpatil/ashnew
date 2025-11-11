"""Hybrid controller that combines alpha-beta and MCTS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..game import JumpWindow, Position, RuleConfig
from ..graphs import DiGraph
from .alphabeta import AlphaBetaEngine, SearchResult
from .mcts import MCTSEngine


@dataclass
class HybridSettings:
    depth: int = 4
    mcts_iterations: int = 500
    iter_ms: int = 800
    rollout_depth: int = 24


class HybridEngine:
    def __init__(self) -> None:
        self.ab = AlphaBetaEngine()
        self.mcts = MCTSEngine()
        self.last_result: Optional[SearchResult] = None

    def choose_move(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        pos: Position,
        *,
        config: RuleConfig,
        jump_window: Optional[JumpWindow],
        settings: HybridSettings,
        seed: Optional[int] = None,
    ):
        move_ab = self.ab.search(
            graph_a,
            graph_b,
            pos,
            config=config,
            jump_window=jump_window,
            max_depth=settings.depth,
            time_limit_ms=settings.iter_ms,
            seed=seed,
        )
        self.last_result = move_ab

        # Use MCTS as tie-breaker or for high branching factor
        branching = len(move_ab.pv)
        if branching > 3:
            self.mcts.rollout_depth = settings.rollout_depth
            move = self.mcts.search(
                graph_a,
                graph_b,
                pos,
                config=config,
                jump_window=jump_window,
                iterations=settings.mcts_iterations,
                seed=seed,
            )
            return move
        return move_ab.move


__all__ = ["HybridEngine", "HybridSettings"]
