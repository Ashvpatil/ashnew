# Two-Way Global Bisimulation Game

An interactive PySide6 desktop application showcasing the Two-Way Global
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
- P – toggle principal variation overlay
- M – toggle MCTS heatmap overlay
- R – replay current game
- Ctrl+S / Ctrl+O – save/load sessions
- Ctrl+Z / Ctrl+Y – undo/redo
- Shift+H – high-contrast theme

## Switching UI Stack

The project is built with PySide6. To adapt to PyQt5 or other toolkits, replace
imports under `twgbg/gui` and update `pyproject.toml` dependencies accordingly.
