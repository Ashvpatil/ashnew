"""Tkinter front-end for the Two-Way Global Bisimulation Game."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Dict, List, Optional

from ..engine import graphs
from ..engine.game import Move, Position, RuleConfig, legal_responses, spoiler_legal_moves
from ..engine.notation import serialize
from ..engine.utils import DeterministicRNG
from ..engine.ai import AlphaBetaAI, MCTSAI, HybridAI
from .graphview import GraphCanvas
from .panels import AISettings, HintPanel, RulePanel
from .themes import ThemeManager
from .tutorial import Tutorial

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_graphs"
PUZZLE_DIR = Path(__file__).resolve().parent.parent / "puzzles" / "preset_games"


class TWGBGApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self.theme = ThemeManager(master)
        master.title("Two-Way Global Bisimulation Game")
        master.geometry("1200x800")
        self.pack(fill="both", expand=True)
        self.rule_config = RuleConfig()
        self.ai_engine: str = "hybrid"
        self.ai_map = {
            "alphabeta": AlphaBetaAI(),
            "mcts": MCTSAI(),
            "hybrid": HybridAI(),
        }
        self.graph_a, start_a = graphs.path_graph(4, prefix="A")
        self.graph_b, start_b = graphs.path_graph(4, prefix="B")
        self.position = Position(start_a, start_b)
        self.history: List[Move] = []
        self.pending_move: Optional[Move] = None
        self.round_no = 0
        self.spoiler_last_side: Optional[str] = None
        self._build_ui()
        self._refresh_canvas()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="New path", command=self._new_path).pack(side="left", padx=4)
        ttk.Button(top, text="New random", command=self._new_random).pack(side="left", padx=4)
        ttk.Button(top, text="Load sample", command=self._load_sample).pack(side="left", padx=4)
        ttk.Button(top, text="Spoiler move", command=self._spoiler_move).pack(side="left", padx=12)
        ttk.Button(top, text="Undo", command=self._undo).pack(side="left", padx=4)
        ttk.Button(top, text="Export history", command=self._export_history).pack(side="left", padx=4)
        ttk.Button(top, text="Theme", command=self._cycle_theme).pack(side="right", padx=4)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Play tab
        play = ttk.Frame(notebook)
        notebook.add(play, text="Play")
        left = ttk.Frame(play)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = GraphCanvas(left)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.set_click_callback(self._node_clicked)
        right = ttk.Frame(play, width=220)
        right.pack(side="right", fill="y")
        self.rule_panel = RulePanel(right, self._update_rules)
        self.rule_panel.pack(fill="x", pady=4)
        self.ai_panel = AISettings(right, self._set_engine)
        self.ai_panel.pack(fill="x", pady=4)
        self.hint_panel = HintPanel(right)
        self.hint_panel.pack(fill="x", pady=4)
        ttk.Label(right, text="Status:").pack(anchor="w", pady=(8, 0))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(right, textvariable=self.status_var, wraplength=200).pack(fill="x")

        # Tutorial tab
        tutorial_tab = Tutorial(notebook)
        notebook.add(tutorial_tab, text="Learn")

        # Analysis tab
        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Analysis & Coach")
        ttk.Label(analysis_tab, text="Coach Summary", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=6)
        self.coach_var = tk.StringVar(value="Spoiler hints appear after each AI move.")
        ttk.Label(analysis_tab, textvariable=self.coach_var, wraplength=600, justify="left").pack(anchor="w", padx=10)

        # Experiments tab placeholder
        experiments_tab = ttk.Frame(notebook)
        notebook.add(experiments_tab, text="Experiments")
        ttk.Label(experiments_tab, text="Run experiments from the command line:").pack(anchor="w", pady=6)
        ttk.Label(
            experiments_tab,
            text="python -m twgbg.experiments.run --games 50 --mode hybrid --depth 4",
        ).pack(anchor="w", padx=10)

        master.bind("<space>", lambda e: self._spoiler_move())
        master.bind("<Control-z>", lambda e: self._undo())

    # Rule updates
    def _update_rules(self, config: RuleConfig) -> None:
        self.rule_config = config

    def _set_engine(self, name: str) -> None:
        self.ai_engine = name

    # Graph loading
    def _new_path(self) -> None:
        self.graph_a, start_a = graphs.path_graph(5, prefix="A")
        self.graph_b, start_b = graphs.path_graph(5, prefix="B")
        self._reset_position(start_a, start_b)

    def _new_random(self) -> None:
        rng = DeterministicRNG()
        self.graph_a, start_a = graphs.random_digraph(6, 0.3, prefix="A")
        self.graph_b, start_b = graphs.random_digraph(6, 0.3, prefix="B")
        self._reset_position(start_a, start_b)

    def _load_sample(self) -> None:
        files = list(DATA_DIR.glob("*.json"))
        if not files:
            return
        data = json.loads(files[0].read_text())
        self.graph_a, start_a = graphs.dict_to_graph(data)
        self.graph_b, start_b = graphs.dict_to_graph(data)
        self._reset_position(start_a or "A1", start_b or "A1")

    def _reset_position(self, start_a: str, start_b: str) -> None:
        self.position = Position(start_a, start_b)
        self.history.clear()
        self.pending_move = None
        self.round_no = 0
        self.spoiler_last_side = None
        self.canvas.set_graphs(self.graph_a, self.graph_b, self.position)
        self._refresh_canvas()
        self.status_var.set("New game ready")

    def _export_history(self) -> None:
        path = Path("history.json")
        path.write_text(json.dumps({"notation": serialize(self.history)}, indent=2))
        self.status_var.set(f"Exported {path}")

    # Gameplay
    def _spoiler_move(self) -> None:
        if self.pending_move is not None:
            self.status_var.set("Complete current reply first")
            return
        ai = self.ai_map[self.ai_engine]
        move = ai.select_move(
            self.graph_a,
            self.graph_b,
            self.position,
            self.rule_config,
            self.history,
            self.round_no,
            self.spoiler_last_side,
        )
        self.pending_move = move
        hints = self._responses_for_move(move)
        hint_map = {f"{i+1}": dest for i, dest in enumerate(hints)}
        self.hint_panel.update_hints(hint_map)
        self.status_var.set(f"Spoiler plays {move.side}:{move.mtype}->{move.dest}")
        self.coach_var.set(
            f"Spoiler threatened {len(hints)} replies. Choose wisely!"
        )
        heatmap = getattr(ai, "visit_counts", {})
        pv = getattr(ai, "pv", [])
        if move.side == "A":
            hints_a = []
            hints_b = hints
        else:
            hints_a = hints
            hints_b = []
        self.canvas.update_state(self.position, hints_a, hints_b, pv, heatmap)

    def _responses_for_move(self, move: Move) -> List[str]:
        other_graph = self.graph_b if move.side == "A" else self.graph_a
        other_curr = self.position.B_curr if move.side == "A" else self.position.A_curr
        return legal_responses(other_graph, other_curr, move.mtype)

    def _node_clicked(self, side: str, node: str) -> None:
        if self.pending_move is None:
            return
        move = self.pending_move
        if side == move.side:
            return
        legal = self._responses_for_move(move)
        if node not in legal:
            self.status_var.set(f"{node} is not a legal reply")
            return
        if move.side == "A":
            self.position = Position(move.dest, node)
        else:
            self.position = Position(node, move.dest)
        self.history.append(move)
        self.history.append(Move("B" if move.side == "A" else "A", move.mtype, node))
        self.pending_move = None
        self.round_no += 1
        self.spoiler_last_side = move.side
        self.hint_panel.update_hints({})
        self.status_var.set("Duplicator survived this round")
        self._refresh_canvas()

    def _undo(self) -> None:
        if len(self.history) < 2:
            return
        self.history.pop()
        self.history.pop()
        self.round_no = max(0, self.round_no - 1)
        self.pending_move = None
        self._recompute_position()
        self._refresh_canvas()

    def _recompute_position(self) -> None:
        if not self.history:
            return
        cursor = Position(self.position.A_curr, self.position.B_curr)
        start_a = self.history[0].dest if self.history[0].side == "A" else self.position.A_curr
        start_b = self.history[1].dest if len(self.history) > 1 and self.history[1].side == "B" else self.position.B_curr
        cursor = Position(start_a, start_b)
        for i in range(0, len(self.history), 2):
            spoiler = self.history[i]
            reply = self.history[i + 1] if i + 1 < len(self.history) else None
            if spoiler.side == "A" and reply:
                cursor = Position(spoiler.dest, reply.dest if reply else cursor.B_curr)
            elif spoiler.side == "B" and reply:
                cursor = Position(reply.dest if reply else cursor.A_curr, spoiler.dest)
        self.position = cursor

    def _refresh_canvas(self) -> None:
        self.canvas.set_graphs(self.graph_a, self.graph_b, self.position)
        self.canvas.update_state(self.position, [], [], [], {})

    def _cycle_theme(self) -> None:
        names = list(self.theme.style.theme_names())
        palette = list(self.theme.palette().keys())
        order = ["dark", "high_contrast", "colorblind"]
        idx = order.index(self.theme.current) if self.theme.current in order else 0
        self.theme.apply(order[(idx + 1) % len(order)])


def main() -> None:  # pragma: no cover
    root = tk.Tk()
    app = TWGBGApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
