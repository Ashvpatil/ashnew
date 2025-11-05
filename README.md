# Two-Way Global Bisimulation Game

An interactive PyQt5 desktop application showcasing the Two-Way Global
Bisimulation Game between Spoiler (AI) and Duplicator (human).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python -m twgbg.gui.app
```

## Packaging

```bash
pyinstaller pyinstaller.spec
```

## Keyboard Shortcuts

- Space – request AI Spoiler move
- H – highlight current legal replies
- M – toggle MCTS heatmap overlay
- R – replay current game
- Ctrl+S / Ctrl+O – save/load sessions
- Ctrl+Z / Ctrl+Y – undo/redo
- Shift+H – high-contrast theme
- P – toggle principal variation overlay
- Toggle colorblind-safe palette from the overlays panel

## Highlights

- Three Spoiler engines: alpha-beta with heuristics, MCTS, and a hybrid controller.
- Always-on hint panel with animated halos in both graph views.
- Coach commentary, alternatives, and bisimulation diagnostics in the Analysis tab.
- Guided onboarding tutorial for newcomers and in-app experiment runner.
- Rule variants: mirror mode, jump cooldowns/limits, forced sides, and round limits.

## Switching UI Stack

The project is built with PyQt5. To migrate to another Qt binding or GUI
toolkit:

1. Replace imports under `twgbg/gui` with the target framework equivalents.
2. Update `requirements.txt`, `pyproject.toml`, and `pyinstaller.spec` to list
   the new dependency.
3. Re-test the application entry point (`python -m twgbg.gui.app`) and adjust
   styles in `twgbg/gui/themes.py` if the colour constants differ.
