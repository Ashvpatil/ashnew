# Experiments Guide

This document outlines how to reproduce the experiments reported in the dissertation.

## Environment
- Python 3.10+
- Optional: install `z3-solver` for SMT verification

```bash
pip install -r requirements.txt
```

## Running Batch Games

```bash
python -m twgbg.experiments.run --games 100 --mode alphabeta --depth 5 --csv alphabeta.csv
python -m twgbg.experiments.run --games 100 --mode mcts --rollouts 1500 --playout 40 --c_puct 1.2 --csv mcts.csv
```

Each command prints a JSON summary containing aggregate win rate, average number of rounds, and total runtime.

## Analysing Results
1. Import CSV results into your analysis tool of choice (Python/pandas, R, Excel).
2. Compute descriptive statistics:
   - Win rate with confidence intervals
   - Average depth reached (from log files, optional)
   - Runtime distribution
3. Plot the empirical cumulative distribution of game lengths.

## Suggested Benchmarks
- `--preset sample_duel.json` — deterministic late-game puzzle
- `--games 50 --mode mcts --rollouts 800` — stochastic comparison
- `--games 20 --mode alphabeta --depth 6` — stress test for the transposition table

## Logging Principal Variations
Enable the *Explain* button in the GUI to capture principal variations and rationale. Export saved states for qualitative analysis.
