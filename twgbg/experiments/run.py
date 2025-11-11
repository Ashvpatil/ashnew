"""Batch experiments for the TWGBG engines."""
from __future__ import annotations

import argparse
import csv
import statistics
import time
from dataclasses import dataclass
from typing import List, Tuple

from ..engine.game import JumpWindow, Move, Position, RuleConfig, legal_responses, spoiler_legal_moves, step
from ..engine.graphs import load_json
from ..engine.ai.alphabeta import AlphaBetaEngine
from ..engine.ai.hybrid import HybridEngine, HybridSettings
from ..engine.ai.mcts import MCTSEngine
from ..engine.utils import RNG


@dataclass
class GameRecord:
    spoiler_forced_loss: int
    rounds: int
    engine_time_ms: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TWGBG spoiler AI experiments")
    parser.add_argument("--games", type=int, default=10, help="Number of games to simulate")
    parser.add_argument("--mode", choices=["alphabeta", "mcts", "hybrid"], default="hybrid")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--iter_ms", type=int, default=900)
    parser.add_argument("--rollouts", type=int, default=1200)
    parser.add_argument("--playout", type=int, default=32)
    parser.add_argument("--c_puct", type=float, default=1.414)
    parser.add_argument("--csv", type=str, default="results.csv")
    parser.add_argument("--seed", type=int, default=1)
    return parser.parse_args()


def run_single_game(
    mode: str,
    engine,
    graph_a,
    graph_b,
    start: Position,
    config: RuleConfig,
    *,
    depth: int,
    iter_ms: int,
    rollouts: int,
    playout: int,
    c_puct: float,
    rng: RNG,
) -> GameRecord:
    position = start
    jump_window = JumpWindow(history=[], limit=config.jump_cooldown)
    rounds = 0
    spoiler_won = False
    total_engine_time = 0.0
    while True:
        rounds += 1
        if mode == "alphabeta":
            result = engine.search(
                graph_a,
                graph_b,
                position,
                config=config,
                jump_window=jump_window,
                max_depth=depth,
                time_limit_ms=iter_ms,
            )
            move = result.move
            total_engine_time += result.stats.duration_ms
        elif mode == "mcts":
            start_time = time.perf_counter()
            engine.rollout_depth = playout
            move = engine.search(
                graph_a,
                graph_b,
                position,
                config=config,
                jump_window=jump_window,
                iterations=rollouts,
            )
            total_engine_time += (time.perf_counter() - start_time) * 1000
        else:
            settings = HybridSettings(depth=depth, iter_ms=iter_ms, mcts_iterations=rollouts, rollout_depth=playout)
            start_time = time.perf_counter()
            move = engine.choose_move(
                graph_a,
                graph_b,
                position,
                config=config,
                jump_window=jump_window,
                settings=settings,
            )
            total_engine_time += (time.perf_counter() - start_time) * 1000
        if move is None:
            break
        target_graph = graph_b if move.side == "A" else graph_a
        replies = legal_responses(target_graph, position, move, config)
        if not replies:
            spoiler_won = True
            break
        reply = rng.choice(replies)
        position, alive, info = step(
            graph_a,
            graph_b,
            position,
            move,
            reply,
            config=config,
            jump_window=jump_window,
            round_number=rounds,
        )
        if "Spoiler wins" in info:
            spoiler_won = True
            break
        if not alive:
            spoiler_won = False
            break
        if config.round_limit and rounds >= config.round_limit:
            break
        if rounds > 150:
            break
    return GameRecord(spoiler_forced_loss=1 if spoiler_won else 0, rounds=rounds, engine_time_ms=total_engine_time)


def main() -> None:
    args = parse_args()
    config = RuleConfig()
    graph_a = load_json("twgbg/data/sample_graphs/graph0.json")
    graph_b = load_json("twgbg/data/sample_graphs/graph1.json")
    start = Position(graph_a.vertices()[0], graph_b.vertices()[0])
    rng = RNG(args.seed)
    if args.mode == "alphabeta":
        engine = AlphaBetaEngine()
    elif args.mode == "mcts":
        engine = MCTSEngine(c_puct=args.c_puct, rollout_depth=args.playout)
    else:
        engine = HybridEngine()
    records: List[GameRecord] = []
    for _ in range(args.games):
        record = run_single_game(
            args.mode,
            engine,
            graph_a,
            graph_b,
            start,
            config,
            depth=args.depth,
            iter_ms=args.iter_ms,
            rollouts=args.rollouts,
            playout=args.playout,
            c_puct=args.c_puct,
            rng=rng,
        )
        records.append(record)
    with open(args.csv, "w", newline="", encoding="utf8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["game", "spoiler_forced_loss", "rounds", "engine_time_ms"])
        for idx, rec in enumerate(records):
            writer.writerow([idx, rec.spoiler_forced_loss, rec.rounds, f"{rec.engine_time_ms:.2f}"])
    win_rate = sum(r.spoiler_forced_loss for r in records) / len(records)
    rounds_mean = statistics.mean(r.rounds for r in records)
    rounds_std = statistics.pstdev(r.rounds for r in records) if len(records) > 1 else 0.0
    print(
        f"Win rate {win_rate:.2%} | Avg rounds {rounds_mean:.2f} ± {rounds_std:.2f} | "
        f"Mean engine ms {statistics.mean(r.engine_time_ms for r in records):.1f}"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
