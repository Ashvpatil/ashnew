"""Tkinter front-end for the Two-Way Global Bisimulation Game."""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from ..engine import graphs
from ..engine.game import Move, Position, RuleConfig, legal_responses
from ..engine.notation import serialize
from ..engine.ai import AlphaBetaAI, HybridAI, MCTSAI
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
        self.master.title("Two-Way Global Bisimulation Game")
        self.master.geometry("1200x800")
        self.pack(fill="both", expand=True)

        self.rule_config = RuleConfig()
        self.ai_engine: str = "hybrid"
        self.ai_map = {
            "alphabeta": AlphaBetaAI(),
            "mcts": MCTSAI(),
            "hybrid": HybridAI(),
        }

        base_a, start_a = graphs.path_graph(4, prefix="A")
        base_b, start_b = graphs.path_graph(4, prefix="B")
        self.graph_a = graphs.normalize_labels_to_str(base_a)
        self.graph_b = graphs.normalize_labels_to_str(base_b)
        start_a_str = str(start_a)
        start_b_str = str(start_b)
        self.position = Position(start_a_str, start_b_str)
        self.initial_position = Position(start_a_str, start_b_str)

        self.history: List[Move] = []
        self.pending_move: Optional[Move] = None
        self.round_no = 0
        self.spoiler_last_side: Optional[str] = None
        self.redo_stack: List[Tuple[Move, Move]] = []

        self.hints_enabled = True
        self.pv_enabled = True
        self.hints_a_current: List[str] = []
        self.hints_b_current: List[str] = []
        self.current_pv: List[Move] = []
        self.current_heatmap: Dict[Tuple[str, str], int] = {}

        self._replay_job: Optional[str] = None
        self._replay_moves: List[Move] = []
        self._replay_index = 0
        self._replay_position = self.position

        self._build_ui()
        self.canvas.set_graphs(self.graph_a, self.graph_b, self.position)
        self.canvas.set_overlays(hints=self.hints_enabled, pv=self.pv_enabled)
        self._update_canvas_state()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="New path", command=self._new_path).pack(side="left", padx=4)
        ttk.Button(top, text="New random", command=self._new_random).pack(side="left", padx=4)
        ttk.Button(top, text="Load sample", command=self._load_sample).pack(side="left", padx=4)
        ttk.Button(top, text="Load session", command=self._load_session).pack(side="left", padx=4)
        ttk.Button(top, text="Save session", command=self._save_session).pack(side="left", padx=4)
        ttk.Button(top, text="Spoiler move", command=self._spoiler_move).pack(side="left", padx=12)
        ttk.Button(top, text="Undo", command=self._undo).pack(side="left", padx=4)
        ttk.Button(top, text="Redo", command=self._redo).pack(side="left", padx=4)
        ttk.Button(top, text="Replay", command=self._start_replay).pack(side="left", padx=4)
        ttk.Button(top, text="Export history", command=self._export_history).pack(side="left", padx=4)
        ttk.Button(top, text="Theme", command=self._cycle_theme).pack(side="right", padx=4)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        play = ttk.Frame(notebook)
        notebook.add(play, text="Play")
        left = ttk.Frame(play)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = GraphCanvas(left)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.set_click_callback(self._node_clicked)

        right = ttk.Frame(play, width=240)
        right.pack(side="right", fill="y")
        self.rule_panel = RulePanel(right, self._update_rules)
        self.rule_panel.pack(fill="x", pady=4)
        self.ai_panel = AISettings(right, self._set_engine)
        self.ai_panel.pack(fill="x", pady=4)
        self.hint_panel = HintPanel(right)
        self.hint_panel.pack(fill="x", pady=4)
        ttk.Label(right, text="Status:").pack(anchor="w", pady=(8, 0))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(right, textvariable=self.status_var, wraplength=220).pack(fill="x")

        tutorial_tab = Tutorial(notebook)
        notebook.add(tutorial_tab, text="Learn")

        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Analysis & Coach")
        ttk.Label(analysis_tab, text="Coach Summary", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=6)
        self.coach_var = tk.StringVar(value="Spoiler hints appear after each AI move.")
        ttk.Label(analysis_tab, textvariable=self.coach_var, wraplength=600, justify="left").pack(anchor="w", padx=10)

        experiments_tab = ttk.Frame(notebook)
        notebook.add(experiments_tab, text="Experiments")
        ttk.Label(experiments_tab, text="Run experiments from the command line:").pack(anchor="w", pady=6)
        ttk.Label(
            experiments_tab,
            text="python -m twgbg.experiments.run --games 50 --mode hybrid --depth 4",
        ).pack(anchor="w", padx=10)

        self.hint_panel.set_enabled(self.hints_enabled)
        self.hint_panel.update_hints({})

        self.master.bind("<space>", lambda e: self._spoiler_move())
        self.master.bind("<Key-h>", lambda e: self._toggle_hints())
        self.master.bind("<Key-p>", lambda e: self._toggle_pv())
        self.master.bind("<Key-r>", lambda e: self._start_replay())
        self.master.bind("<Control-s>", lambda e: self._save_session())
        self.master.bind("<Control-o>", lambda e: self._load_session())
        self.master.bind("<Control-z>", lambda e: self._undo())
        self.master.bind("<Control-y>", lambda e: self._redo())

    def _update_rules(self, config: RuleConfig) -> None:
        self.rule_config = config

    def _set_engine(self, name: str) -> None:
        if name in self.ai_map:
            self.ai_engine = name
            if self.ai_panel.engine.get() != name:
                self.ai_panel.engine.set(name)

    def _select_start(self, graph: graphs.DiGraph, candidate: Optional[str]) -> str:
        if candidate is not None:
            candidate_str = str(candidate)
            if candidate_str in graph.succ:
                return candidate_str
        if graph.succ:
            return next(iter(sorted(graph.succ.keys())))
        raise ValueError("Graph has no vertices")

    def _apply_new_graphs(
        self,
        graph_a: graphs.DiGraph,
        start_a: Optional[str],
        graph_b: graphs.DiGraph,
        start_b: Optional[str],
        *,
        message: str = "New game ready",
    ) -> bool:
        normalized_a = graphs.normalize_labels_to_str(graph_a)
        normalized_b = graphs.normalize_labels_to_str(graph_b)
        try:
            start_a_str = self._select_start(normalized_a, start_a)
            start_b_str = self._select_start(normalized_b, start_b)
        except ValueError as exc:
            messagebox.showerror("Graph error", str(exc))
            return False
        self.graph_a = normalized_a
        self.graph_b = normalized_b
        self._reset_position(start_a_str, start_b_str, message=message)
        return True

    def _new_path(self) -> None:
        graph_a, start_a = graphs.path_graph(5, prefix="A")
        graph_b, start_b = graphs.path_graph(5, prefix="B")
        if self._apply_new_graphs(graph_a, start_a, graph_b, start_b, message="New path graphs ready"):
            self.status_var.set("Generated new path graphs")

    def _new_random(self) -> None:
        graph_a, start_a = graphs.random_digraph(6, 0.3, prefix="A")
        graph_b, start_b = graphs.random_digraph(6, 0.3, prefix="B")
        if self._apply_new_graphs(graph_a, start_a, graph_b, start_b, message="Random graphs ready"):
            self.status_var.set("Generated random graphs")

    def _load_sample(self) -> None:
        path = filedialog.askopenfilename(
            title="Load sample graph",
            initialdir=DATA_DIR,
            filetypes=[("JSON", "*.json")],
            parent=self.master,
        )
        if not path:
            self.status_var.set("Load cancelled")
            return
        try:
            graph, start = graphs.load_json(path)
        except Exception as exc:  # pragma: no cover - user facing
            messagebox.showerror("Load failed", str(exc))
            return
        if self._apply_new_graphs(graph, start, graph.copy(), start, message=f"Loaded {Path(path).name}"):
            self.status_var.set(f"Loaded sample {Path(path).name}")

    def _reset_position(self, start_a: str, start_b: str, *, message: Optional[str] = "New game ready") -> None:
        self._stop_replay()
        self.position = Position(str(start_a), str(start_b))
        self.initial_position = Position(str(start_a), str(start_b))
        self.history.clear()
        self.pending_move = None
        self.round_no = 0
        self.spoiler_last_side = None
        self.redo_stack.clear()
        self._reset_hint_state()
        self.canvas.set_graphs(self.graph_a, self.graph_b, self.position)
        self._update_canvas_state()
        if message is not None and hasattr(self, "status_var"):
            self.status_var.set(message)
        if hasattr(self, "coach_var"):
            self.coach_var.set("Spoiler hints appear after each AI move.")

    def _reset_hint_state(self) -> None:
        self.hints_a_current = []
        self.hints_b_current = []
        self.current_pv = []
        self.current_heatmap = {}
        if hasattr(self, "hint_panel"):
            self.hint_panel.update_hints({})

    def _update_canvas_state(self) -> None:
        self.canvas.update_state(
            self.position,
            self.hints_a_current,
            self.hints_b_current,
            self.current_pv,
            self.current_heatmap,
        )

    def _export_history(self) -> None:
        path = Path("history.json")
        path.write_text(json.dumps({"notation": serialize(self.history)}, indent=2))
        self.status_var.set(f"Exported history to {path}")

    def _save_session(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save session",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            parent=self.master,
        )
        if not path:
            self.status_var.set("Save cancelled")
            return
        data = {
            "graph_a": graphs.graph_to_dict(self.graph_a, self.initial_position.A_curr),
            "graph_b": graphs.graph_to_dict(self.graph_b, self.initial_position.B_curr),
            "history": [asdict(m) for m in self.history],
            "rule_config": asdict(self.rule_config),
            "ai_engine": self.ai_engine,
        }
        try:
            Path(path).write_text(json.dumps(data, indent=2))
        except Exception as exc:  # pragma: no cover - user facing
            messagebox.showerror("Save failed", str(exc))
            return
        self.status_var.set(f"Saved session to {Path(path).name}")

    def _load_session(self) -> None:
        path = filedialog.askopenfilename(
            title="Load session",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            parent=self.master,
        )
        if not path:
            self.status_var.set("Load cancelled")
            return
        try:
            payload = json.loads(Path(path).read_text())
        except Exception as exc:  # pragma: no cover - user facing
            messagebox.showerror("Load failed", str(exc))
            return
        try:
            graph_a_data = payload["graph_a"]
            graph_b_data = payload["graph_b"]
        except KeyError as exc:
            messagebox.showerror("Load failed", f"Missing key: {exc}")
            return
        graph_a, start_a = graphs.dict_to_graph(graph_a_data)
        graph_b, start_b = graphs.dict_to_graph(graph_b_data)
        if not self._apply_new_graphs(graph_a, start_a, graph_b, start_b, message=f"Loaded {Path(path).name}"):
            return
        history_payload = payload.get("history", [])
        self.history = []
        for entry in history_payload:
            try:
                move = Move(entry["side"], entry["mtype"], str(entry["dest"]))
            except (KeyError, TypeError):
                continue
            self.history.append(move)
        rule_data = payload.get("rule_config", {})
        if isinstance(rule_data, dict):
            valid = {k: rule_data[k] for k in RuleConfig.__dataclass_fields__ if k in rule_data}
            try:
                self.rule_config = RuleConfig(**valid)
            except TypeError:
                self.rule_config = RuleConfig()
            self.rule_panel.allow_backward.set(self.rule_config.allow_backward)
            self.rule_panel.allow_jump.set(self.rule_config.allow_jump)
            force_value = self.rule_config.force_same_graph or "None"
            self.rule_panel.force_same_graph.set(force_value)
            self.rule_panel.round_limit.set(self.rule_config.round_limit or 0)
        engine_name = payload.get("ai_engine", self.ai_engine)
        if engine_name in self.ai_map:
            self.ai_engine = engine_name
            if self.ai_panel.engine.get() != engine_name:
                self.ai_panel.engine.set(engine_name)
        self.redo_stack.clear()
        self.pending_move = None
        self._reset_hint_state()
        self._recompute_position()
        self._update_canvas_state()
        self.status_var.set(f"Loaded session {Path(path).name}")

    def _responses_for_move(self, move: Move) -> List[str]:
        other_graph = self.graph_b if move.side == "A" else self.graph_a
        other_curr = self.position.B_curr if move.side == "A" else self.position.A_curr
        responses = legal_responses(other_graph, other_curr, move.mtype)
        return [str(r) for r in responses]

    def _spoiler_move(self) -> None:
        if self.pending_move is not None:
            self.status_var.set("Complete the current reply first")
            return
        self._stop_replay()
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
        hint_map = {f"{i + 1}": dest for i, dest in enumerate(hints)}
        self.hint_panel.update_hints(hint_map)
        if move.side == "A":
            self.hints_a_current = []
            self.hints_b_current = hints
        else:
            self.hints_a_current = hints
            self.hints_b_current = []
        heatmap_raw = getattr(ai, "visit_counts", {})
        self.current_heatmap = {}
        if hasattr(heatmap_raw, "items"):
            for (side, node), count in heatmap_raw.items():
                self.current_heatmap[(str(side), str(node))] = int(count)
        pv_moves = getattr(ai, "pv", [])
        self.current_pv = list(pv_moves) if pv_moves else []
        self.redo_stack.clear()
        self.status_var.set(f"Spoiler plays {move.side}:{move.mtype}->{move.dest}")
        self.coach_var.set(f"Spoiler threatened {len(hints)} replies. Choose wisely!")
        self._update_canvas_state()

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
        self.round_no = len(self.history) // 2
        self.spoiler_last_side = move.side
        self.redo_stack.clear()
        self._reset_hint_state()
        self.status_var.set("Duplicator survived this round")
        self._update_canvas_state()

    def _undo(self) -> None:
        if len(self.history) < 2:
            self.status_var.set("Nothing to undo")
            return
        self._stop_replay()
        reply = self.history.pop()
        spoiler = self.history.pop()
        self.redo_stack.append((spoiler, reply))
        self.pending_move = None
        self._reset_hint_state()
        self._recompute_position()
        self.status_var.set("Undid last round")
        self._update_canvas_state()

    def _redo(self) -> None:
        if not self.redo_stack:
            self.status_var.set("Nothing to redo")
            return
        self._stop_replay()
        spoiler, reply = self.redo_stack.pop()
        self.history.append(spoiler)
        self.history.append(reply)
        self.pending_move = None
        self._reset_hint_state()
        self._recompute_position()
        self.status_var.set("Redid round")
        self._update_canvas_state()

    def _recompute_position(self) -> None:
        cursor = Position(self.initial_position.A_curr, self.initial_position.B_curr)
        for move in self.history:
            cursor = self._apply_move_to_position(cursor, move)
        self.position = cursor
        self.round_no = len(self.history) // 2
        if len(self.history) >= 2:
            self.spoiler_last_side = self.history[-2].side
        elif self.history:
            self.spoiler_last_side = self.history[-1].side
        else:
            self.spoiler_last_side = None

    def _toggle_hints(self) -> None:
        self.hints_enabled = not self.hints_enabled
        self.hint_panel.set_enabled(self.hints_enabled)
        self.canvas.set_overlays(hints=self.hints_enabled)
        self.status_var.set("Hints enabled" if self.hints_enabled else "Hints hidden")

    def _toggle_pv(self) -> None:
        self.pv_enabled = not self.pv_enabled
        self.canvas.set_overlays(pv=self.pv_enabled)
        self.status_var.set("PV overlay enabled" if self.pv_enabled else "PV overlay hidden")

    def _start_replay(self) -> None:
        if self.pending_move is not None:
            self.status_var.set("Finish the current move before replay")
            return
        if not self.history:
            self.status_var.set("No moves to replay")
            return
        self._stop_replay()
        self._replay_moves = list(self.history)
        self._replay_index = 0
        self._replay_position = Position(self.initial_position.A_curr, self.initial_position.B_curr)
        self.position = Position(self.initial_position.A_curr, self.initial_position.B_curr)
        self._reset_hint_state()
        self.status_var.set("Replaying history…")
        self._update_canvas_state()
        self._schedule_next_replay()

    def _schedule_next_replay(self) -> None:
        if self._replay_index >= len(self._replay_moves):
            self._finish_replay("Replay complete")
            self._recompute_position()
            self._update_canvas_state()
            return
        move = self._replay_moves[self._replay_index]
        self._replay_position = self._apply_move_to_position(self._replay_position, move)
        self.position = self._replay_position
        self._update_canvas_state()
        self._replay_index += 1
        self._replay_job = self.master.after(500, self._schedule_next_replay)

    def _stop_replay(self) -> None:
        if self._replay_job is not None:
            self.master.after_cancel(self._replay_job)
            self._replay_job = None
        self._replay_moves = []
        self._replay_index = 0
        self._replay_position = self.position

    def _finish_replay(self, message: str) -> None:
        self._stop_replay()
        self.status_var.set(message)

    @staticmethod
    def _apply_move_to_position(position: Position, move: Move) -> Position:
        if move.dest is None:
            return position
        if move.side == "A":
            return Position(str(move.dest), position.B_curr)
        return Position(position.A_curr, str(move.dest))

    def _cycle_theme(self) -> None:
        names = ["dark", "high_contrast", "colorblind"]
        idx = names.index(self.theme.current) if self.theme.current in names else 0
        self.theme.apply(names[(idx + 1) % len(names)])


def main() -> None:  # pragma: no cover
    root = tk.Tk()
    app = TWGBGApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
