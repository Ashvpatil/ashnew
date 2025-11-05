# Two-Way Global Bisimulation Game Toolkit

This repository provides a fully local implementation of the Two-Way Global Bisimulation Game with an interactive Tkinter user interface, advanced spoiler AIs, analysis helpers and experiment scripts.

## Quickstart

```bash
python -m twgbg.gui.tk_app
```

Run batch experiments:

```bash
python -m twgbg.experiments.run --games 50 --mode hybrid --depth 4 --rollouts 1200 --playout 32 --c_puct 1.414
```

Packaged builds can be produced with the provided `pyinstaller.spec`.

## Project Layout

```
twgbg/
  engine/        # pure game logic, AI engines
  gui/           # Tkinter application
  analysis/      # bisimulation tools
  experiments/   # CLI runners
  data/          # sample graphs
  puzzles/       # preset puzzle definitions
  docs/          # guides and references
```

See `docs/USER_GUIDE.md` for in-depth instructions and troubleshooting tips.
