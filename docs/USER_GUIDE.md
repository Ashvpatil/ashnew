# User Guide

## Installation

1. Ensure Python 3.10 or newer is installed.
2. Clone the repository and install optional dependencies:

```bash
pip install -r requirements.txt
```

## Running the GUI

Launch the interactive Tkinter client:

```bash
python -m twgbg.gui.tk_app
```

### Controls

- **Space** – let the spoiler AI choose the next move.
- **Click highlighted nodes** – supply the duplicator reply.
- **Ctrl+Z** – undo the previous round.
- Use the buttons in the top bar for random/path graphs, exporting, and theming.

### Overlays

- Principal variation lines glow in cyan.
- Heatmaps colour the nodes by MCTS visit counts.
- Always-on hint halos and the legal move panel list valid replies.

## Troubleshooting

- If the window is blank, resize it to trigger a redraw.
- On macOS the mouse wheel delta might be inverted; hold `Ctrl` while scrolling for zoom.
- The optional z3 verifier loads only when `z3-solver` is installed.

## Experiments

Run large batches from the command line:

```bash
python -m twgbg.experiments.run --games 50 --mode hybrid --depth 4 --rollouts 1200 --playout 32 --c_puct 1.414
```

Results are written to CSV with aggregate statistics printed to the console.
