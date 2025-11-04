"""CLI experiments for the Two-Way Global Bisimulation Game."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from ..engine.ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from ..engine.ai.hybrid import HybridConfig, HybridSpoiler
from ..engine.ai.mcts import MCTSConfig, MCTSSpoiler
from ..engine.game import Position, RuleSet, legal_responses, step
from ..engine.graphs import DiGraph, load_graph_pair


@dataclass
class ExperimentResult:
    spoiler_win_rate: float
    avg_rounds: float
    runtime: float


def _play_single(
    engine: str,
    graph_a: DiGraph,
    graph_b: DiGraph,
    rules: RuleSet,
    config: argparse.Namespace,
    rng: random.Random,
) -> Tuple[bool, int]:
    position = Position(graph_a.vertices()[0], graph_b.vertices()[0])
    rounds = 0
    if engine == "alphabeta":
        spoiler = AlphaBetaSpoiler(
            graph_a,
            graph_b,
            rules,
            config=SearchConfig(depth=config.depth, time_budget_ms=config.iter_ms),
        )
        chooser = lambda pos: spoiler.search(pos).best_move  # type: ignore[return-value]
    elif engine == "mcts":
        spoiler = MCTSSpoiler(
            graph_a,
            graph_b,
            rules,
            config=MCTSConfig(
                rollouts=config.rollouts,
                playout_depth=config.playout,
                c_puct=config.c_puct,
            ),
        )
        chooser = lambda pos: spoiler.run(pos).best_move
    else:
        spoiler = HybridSpoiler(
            graph_a,
            graph_b,
            rules,
            config=HybridConfig(
                alphabeta_depth=config.depth,
                alphabeta_time_ms=config.iter_ms,
                mcts_rollouts=config.rollouts,
                mcts_playout_depth=config.playout,
                c_puct=config.c_puct,
            ),
        )
        chooser = lambda pos: spoiler.choose(pos).best_move

    pos = position
    for _ in range(config.max_rounds):
        move = chooser(pos)
        if move is None:
            return False, rounds
        replies = legal_responses(graph_a, graph_b, pos, move, rules)
        if not replies:
            return True, rounds + 1
        reply = rng.choice(replies)
        pos, alive, info = step(graph_a, graph_b, pos, move, reply, rules)
        rounds += 1
        if not alive:
            return info.get("spoiler_wins", False), rounds
    return False, rounds


def run_match(
    graph_a: DiGraph,
    graph_b: DiGraph,
    rules: RuleSet,
    config: argparse.Namespace,
) -> ExperimentResult:
    rng = random.Random(config.seed)
    wins = 0
    total_rounds = 0
    start = dt.datetime.now()
    for _ in range(config.games):
        win, rounds = _play_single(config.mode, graph_a, graph_b, rules, config, rng)
        if win:
            wins += 1
        total_rounds += rounds
    runtime = (dt.datetime.now() - start).total_seconds()
    win_rate = wins / max(1, config.games)
    avg_rounds = total_rounds / max(1, config.games)
    return ExperimentResult(win_rate, avg_rounds, runtime)


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair", help="Path to graph pair JSON")
    parser.add_argument("--games", type=int, default=5, help="Number of games to simulate")
    parser.add_argument("--mode", choices=["alphabeta", "mcts", "hybrid"], default="hybrid")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--iter-ms", dest="iter_ms", type=int, default=2000)
    parser.add_argument("--rollouts", type=int, default=600)
    parser.add_argument("--playout", type=int, default=12)
    parser.add_argument("--c-puct", dest="c_puct", type=float, default=1.414)
    parser.add_argument("--max-rounds", type=int, default=80)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output", type=Path, default=Path("experiments.csv"))
    args = parser.parse_args(argv)

    graph_a, graph_b = load_graph_pair(args.pair)
    rules = RuleSet()
    result = run_match(graph_a, graph_b, rules, args)

    with args.output.open("w", newline="", encoding="utf8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["spoiler_win_rate", "avg_rounds", "runtime"])
        writer.writeheader()
        writer.writerow(result.__dict__)

    print(f"Saved results to {args.output}")


if __name__ == "__main__":
    main()
