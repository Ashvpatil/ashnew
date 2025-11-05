"""Batch experiment runner."""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from dataclasses import dataclass
from typing import List, Sequence

from ..engine.game import Move, Position, RuleConfig
from ..engine.graphs import DiGraph, path_graph
from ..engine.ai import AlphaBetaAI, MCTSAI, HybridAI


AI_MODES = {
    "alphabeta": AlphaBetaAI,
    "mcts": MCTSAI,
    "hybrid": HybridAI,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run spoiler AI experiments")
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--mode", choices=AI_MODES.keys(), default="hybrid")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--iter_ms", type=int, default=800)
    parser.add_argument("--rollouts", type=int, default=800)
    parser.add_argument("--playout", type=int, default=32)
    parser.add_argument("--c_puct", type=float, default=1.414)
    parser.add_argument("--csv", type=str, default="results.csv")
    parser.add_argument("--seed", type=int, default=1)
    return parser.parse_args()


def run_game(ai, graph_a: DiGraph, graph_b: DiGraph, config: RuleConfig) -> int:
    pos = Position(next(iter(graph_a.succ)), next(iter(graph_b.succ)))
    history: List[Move] = []
    rounds = 0
    while True:
        move = ai.select_move(graph_a, graph_b, pos, config, history, rounds, None)
        responses = ai.alphabeta._responses_for_move(graph_a, graph_b, pos, move, config) if hasattr(ai, "alphabeta") else ai._responses_for_move(graph_a, graph_b, pos, move, config)
        if not responses:
            return rounds
        reply = responses[0]
        pos = Position(move.dest, reply) if move.side == "A" else Position(reply, move.dest)
        history.append(move)
        history.append(Move("B" if move.side == "A" else "A", move.mtype, reply))
        rounds += 1


def main() -> None:
    args = parse_args()
    config = RuleConfig()
    graph_a, start_a = path_graph(4, prefix="A")
    graph_b, start_b = path_graph(4, prefix="B")
    ai_cls = AI_MODES[args.mode]
    if args.mode == "alphabeta":
        ai = ai_cls()
    elif args.mode == "mcts":
        ai = ai_cls()
    else:
        ai = ai_cls()
    results: List[int] = []
    t_start = time.perf_counter()
    for _ in range(args.games):
        rounds = run_game(ai, graph_a, graph_b, config)
        results.append(rounds)
    elapsed = (time.perf_counter() - t_start) * 1000
    mean_rounds = statistics.mean(results) if results else 0
    stdev_rounds = statistics.pstdev(results) if len(results) > 1 else 0
    with open(args.csv, "w", newline="", encoding="utf8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rounds"])
        for r in results:
            writer.writerow([r])
    print(f"games={len(results)} mean_rounds={mean_rounds:.2f} stdev={stdev_rounds:.2f} time_ms={elapsed:.0f}")


if __name__ == "__main__":  # pragma: no cover
    main()
