# Two-Way Global Bisimulation Game (TWGBG)

This repository contains a full, desktop-based implementation of the Two-Way
Global Bisimulation Game. The Spoiler is controlled by a suite of advanced AI
engines (alpha–beta, Monte-Carlo tree search and a hybrid orchestrator) while a
human plays as the Duplicator through a rich Tkinter interface.

## Technology Stack

* **Language**: Python 3.10+
* **GUI**: Tkinter/ttk (standard library)
* **AI**: Custom search engines, transposition tables, MCTS, hybrid controller

No external services are required; everything runs locally and offline.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m twgbg.gui.app
```

The GUI launches with sample graphs preloaded. Press `Space` to let the Spoiler
move, then answer as the Duplicator by clicking highlighted nodes or using the
hint chips.

## Packaging with PyInstaller

```
pyinstaller pyinstaller.spec
```

The generated executable bundles the GUI together with data, puzzles and docs.

## Project Highlights

* Two graph canvases with zoom/pan, curved arrow rendering, PV and heatmap
  overlays.
* Alpha–Beta engine featuring iterative deepening, quiescence, killer moves,
  history heuristic and tablebase probes.
* MCTS with UCT exploration, ε-greedy rollouts and visit count tracking.
* Hybrid meta-engine to switch between tree search paradigms based on branching.
* Tutorial, analysis and experiments tabs for onboarding and research.

## Troubleshooting

* If Tkinter cannot find a display (e.g. on headless servers) use a virtual
  framebuffer such as Xvfb.
* The optional `z3-solver` dependency is only required for the optional
  verification module. The application runs without it.

For a detailed walkthrough of the UI refer to `twgbg/docs/USER_GUIDE.md`.
