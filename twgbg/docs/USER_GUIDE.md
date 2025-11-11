# Two-Way Global Bisimulation Game – User Guide

Welcome to the TWGBG desktop application. This guide summarises the most
important concepts so you can start exploring the game and the tooling quickly.

## Objective

Spoiler (AI) attempts to demonstrate a difference between two directed graphs
while Duplicator (you) tries to keep them indistinguishable. In every round the
Spoiler chooses a graph and performs a move. Your task is to answer with a move
of the same type in the opposite graph. If you ever fail to provide a legal
answer you lose, otherwise surviving the configured number of rounds means you
win.

## Application Layout

* **Play tab** – interactively play against the AI. The two force-directed graph
  canvases show graphs A and B. The glowing blue node indicates the current
  vertex. Pulsing green halos mark legal replies. Use the hint chips underneath
  the boards to respond.
* **Tutorial tab** – learn the mechanics step-by-step using plain language
  explanations.
* **Analysis tab** – inspect bisimulation signatures of the current graphs.
* **Experiments tab** – quick link to the batch experiment runner.

## Controls

* `Space` – ask the Spoiler (AI) to make a move.
* `Ctrl+S / Ctrl+O` – save or load a session.
* `Ctrl+Z / Ctrl+Y` – undo or redo the previous round.
* Mouse wheel – zoom in/out of the canvas.
* Middle mouse drag – pan the canvas.
* Left click on a highlighted node – select it as your reply.

## Spoiler Engines

Choose between three engines in the right sidebar:

1. **Alpha-Beta** – deterministic search with iterative deepening and
   transposition tables. Shows principal variation overlays when enabled.
2. **MCTS** – stochastic tree search that provides a visit-count heatmap.
3. **Hybrid** – combines both approaches using time driven heuristics.

Engine overlays can be toggled at any time using the checkboxes.

## Rule Toggles

The rule panel allows you to change optional constraints such as allowing
backward moves, enabling jumps or mirror mode. Settings apply immediately.

## Exporting and Reporting

Use the `File → Export board` command to save PostScript snapshots of the boards.
Results can be embedded into your reports directly. The `twgbg/docs` folder
contains a `REPORT_TEMPLATE.md` scaffold for research style write-ups.

Enjoy exploring the interplay between graph structure and bisimulation!
