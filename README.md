# Two-Way Global Bisimulation Game

A research-grade Python project implementing the two-way global bisimulation game on directed graphs. The package includes a Tkinter GUI, strong Spoiler AI engines (alpha-beta and Monte Carlo tree search), analysis tooling, experiment scripts, and documentation designed for MSc-level dissertations.

## Quick Start

```bash
pip install -r requirements.txt
python -m twgbg.gui.tk_app
```

The GUI lets you play as Duplicator while an AI controls Spoiler. Use the settings panel to switch between the alpha-beta and MCTS engines, toggle rule variants (forward/backward/jump), and visualise heatmaps or principal variations.

## Project Layout
- `twgbg/engine/` – deterministic graph and game logic
- `twgbg/ai/` – alpha-beta search, MCTS, tablebase, symmetry pruning, learning heuristics
- `twgbg/analysis/` – bisimulation diagnostics, witness traces, optional Z3 solver
- `twgbg/experiments/` – batch CLI for automated matches
- `twgbg/gui/` – Tkinter application with analysis/coach features
- `twgbg/data/` – sample graphs, puzzles, preset games
- `docs/` – user guide, experiments manual, report template, literature survey
- `tests/` – lightweight unit tests for engine and AI modules

## Experiments
Run repeated matches to collect statistics:

```bash
python -m twgbg.experiments.run --games 50 --mode mcts --rollouts 1200 --c_puct 1.3 --csv mcts.csv
```

## Packaging
A `pyinstaller.spec` file is provided for building standalone executables. See `docs/USER_GUIDE.md` for details.
