# Two-Way Global Bisimulation Game – User Guide

## Installation

1. Ensure Python 3.10 or later is installed.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Launching the GUI

```bash
python -m twgbg.gui.tk_app
```

Use the buttons in the *Play* tab to generate graphs, request Spoiler moves, and interact as Duplicator by clicking highlighted vertices.

### Controls
- **Space** – trigger Spoiler AI move.
- **H** – request a hint.
- **P** – toggle principal variation overlay.
- **R** – animated replay.
- **Ctrl+S / Ctrl+O** – save or load sessions.
- **Ctrl+Z / Ctrl+Y** – undo / redo.

### Settings
The settings panel adjusts rule toggles, AI engine (Alpha-Beta or MCTS), depth, rollout counts, and heatmap generation.

## Analysis Tools
- Signature partitions display in the *Analysis & Coach* tab.
- Witness traces appear when Spoiler has a forced win within the search horizon.
- Use the *Explain* button to receive textual AI reasoning.

## Command-Line Experiments

```bash
python -m twgbg.experiments.run --games 20 --mode alphabeta --depth 4 --csv runs.csv
```

This prints summary statistics and writes per-game results to CSV.
