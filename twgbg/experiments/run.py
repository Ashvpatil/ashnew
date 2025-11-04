"""CLI utilities for running automated experiments."""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..engine.graphs import DiGraph
from ..engine.game import Move, Position
from ..ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from ..ai.mcts import MCTSSpoiler, MCTSConfig
from ..ai.tablebase import Tablebase

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_graph(path: Path) -> DiGraph:
    with open(path, "r", encoding="utf8") as fh:
        payload = json.load(fh)
    return DiGraph.from_dict(payload)


def random_graph_pair(seed: int, size: int = 6) -> Tuple[DiGraph, DiGraph]:
    rng = random.Random(seed)
    g1 = DiGraph.random_graph(size, 0.4, seed=rng.randint(0, 9999), prefix="a")
    g2 = DiGraph.random_graph(size, 0.4, seed=rng.randint(0, 9999), prefix="b")
    return g1, g2


def duplicator_policy(position: Position, move: Move) -> Move:
    responses = position.legal_responses(move)
    if not responses:
        raise ValueError("Duplicator has no legal move")
    return max(responses, key=lambda m: len(position.legal_responses(m)))


def run_game(position: Position, mode: str, config: argparse.Namespace) -> Tuple[bool, int]:
    tablebase = Tablebase()
    alphabeta = AlphaBetaSpoiler(SearchConfig(max_depth=config.depth, time_budget=1.5), tablebase=tablebase)
    mcts = MCTSSpoiler(
        MCTSConfig(
            iterations=config.rollouts,
            time_budget=config.iter_ms / 1000 if config.iter_ms else 2.0,
            c_puct=config.c_puct,
            rollout_depth=config.playout,
        )
    )
    rounds = 0
    while rounds < 200:
        rounds += 1
        if mode in {"alphabeta", "iterdeep"}:
            info = alphabeta.choose_move(position)
            move = info.best_move
        elif mode == "mcts":
            move, _ = mcts.choose_move(position)
        else:
            raise ValueError(f"unknown mode {mode}")
        if move is None:
            return False, rounds
        responses = position.legal_responses(move)
        if not responses:
            return True, rounds
        reply = duplicator_policy(position, move)
        position = position.step(move, reply)
    return False, rounds


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Two-way bisimulation game experiments")
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--mode", choices=["alphabeta", "iterdeep", "mcts"], default="alphabeta")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--rollouts", type=int, default=500)
    parser.add_argument("--playout", type=int, default=32)
    parser.add_argument("--c_puct", type=float, default=1.414)
    parser.add_argument("--iter_ms", type=int, default=2000)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--preset", type=str, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    results = []
    start = time.time()
    for game_idx in range(args.games):
        if args.preset:
            preset_path = DATA_DIR / "preset_games" / args.preset
            with open(preset_path, "r", encoding="utf8") as fh:
                payload = json.load(fh)
            graph_a = DiGraph.from_dict(payload["graph_a"])
            graph_b = DiGraph.from_dict(payload["graph_b"])
            node_a = payload["node_a"]
            node_b = payload["node_b"]
        else:
            graph_a, graph_b = random_graph_pair(seed=game_idx)
            node_a = next(iter(graph_a.nodes()))
            node_b = next(iter(graph_b.nodes()))
        position = Position(graph_a, graph_b, node_a, node_b)
        spoiler_win, rounds = run_game(position, args.mode, args)
        results.append({"win": spoiler_win, "rounds": rounds})

    win_rate = sum(1 for r in results if r["win"]) / len(results)
    avg_rounds = statistics.mean(r["rounds"] for r in results)
    duration = time.time() - start
    summary = {
        "games": len(results),
        "win_rate": win_rate,
        "avg_rounds": avg_rounds,
        "runtime": duration,
    }
    print(json.dumps(summary, indent=2))

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["game", "win", "rounds"])
            writer.writeheader()
            for idx, result in enumerate(results):
                writer.writerow({"game": idx, **result})


if __name__ == "__main__":  # pragma: no cover
    main()
