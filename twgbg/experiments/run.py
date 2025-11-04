"""Command line experiments for the bisimulation game."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..engine.graphs import DiGraph, load_graph_pair
from ..engine.game import Position, RuleSet
from ..engine.ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from ..engine.ai.mcts import MCTSSpoiler, MCTSConfig


@dataclass
class ExperimentResult:
    win_rate: float
    avg_rounds: float
    runtime: float


def run_match(graph_a: DiGraph, graph_b: DiGraph, rules: RuleSet, rounds: int, search_depth: int) -> ExperimentResult:
    position = Position(graph_a.vertices()[0], graph_b.vertices()[0])
    spoiler = AlphaBetaSpoiler(graph_a, graph_b, rules, config=SearchConfig(depth=search_depth, iterative_deepening=False))
    wins = 0
    total_rounds = 0
    start = dt.datetime.now()
    for _ in range(rounds):
        pos = position
        for ply in range(64):
            result = spoiler.search(pos)
            if result.best_move is None:
                break
            responses = rules.legal_types()
            # For experiments we simulate random duplicator replies.
            from ..engine.game import legal_responses, step

            replies = legal_responses(graph_a, graph_b, pos, result.best_move, rules)
            if not replies:
                wins += 1
                total_rounds += ply + 1
                break
            reply = replies[0]
            pos = step(graph_a, graph_b, pos, result.best_move, reply)
        else:
            total_rounds += 64
    runtime = (dt.datetime.now() - start).total_seconds()
    return ExperimentResult(wins / rounds if rounds else 0.0, total_rounds / max(1, wins), runtime)


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair", help="Path to graph pair JSON")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("experiments.csv"))
    args = parser.parse_args(argv)

    graph_a, graph_b = load_graph_pair(args.pair)
    rules = RuleSet()
    result = run_match(graph_a, graph_b, rules, args.rounds, args.depth)

    with args.output.open("w", newline="", encoding="utf8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["win_rate", "avg_rounds", "runtime"])
        writer.writeheader()
        writer.writerow(result.__dict__)

    print(f"Saved results to {args.output}")


if __name__ == "__main__":
    main()
