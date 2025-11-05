# Experiments

This document summarises how to reproduce the benchmark runs included with the toolkit.

## Setup

1. Install dependencies from `requirements.txt`.
2. Launch runs from the project root.

## Single Batch Example

```bash
python -m twgbg.experiments.run --games 100 --mode hybrid --depth 5 --rollouts 1500 --playout 32 --c_puct 1.2 --csv hybrid.csv
```

The command prints aggregate statistics (mean, standard deviation, min, max) and writes the per-game round counts to `hybrid.csv`.

## Parameter Sweeps

The CLI exposes knobs for depth, rollouts, playout depth, exploration constant, and random seed. Combine with external tooling (GNU Parallel, Snakemake) to sweep large grids and gather CSV outputs for later analysis.

## Analysing Results

- Load the CSV into pandas, R, or spreadsheet software.
- Compare spoiler win rates, average rounds, and runtime.
- Correlate heatmap visit counts (logged in the GUI) with winning strategies to craft new heuristics.
