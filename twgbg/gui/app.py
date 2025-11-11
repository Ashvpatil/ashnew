"""Main Tkinter application for the TWGBG suite."""
from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from ..analysis.bisim import signature_partition
from ..engine.game import JumpWindow, Move, Position, RuleConfig, legal_responses, spoiler_legal_moves, step
from ..engine.graphs import DiGraph, load_json, path_graph, random_digraph
from ..engine.notation import Ply, serialize
from ..engine.ai.alphabeta import AlphaBetaEngine, SearchResult
from ..engine.ai.hybrid import HybridEngine, HybridSettings
from ..engine.ai.mcts import MCTSEngine
from ..engine.ai.learning import LearnedBias
from ..engine.ai.tablebase import Tablebase
from ..engine.utils import format_duration
from .graphview import GraphView
from .panels import RulePanel, ThemePanel
from .themes import THEMES, Theme
from .tutorial import TutorialManager
from .exporter import ask_export_file, save_canvas_png

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_graphs"
PUZZLE_DIR = Path(__file__).resolve().parent.parent / "puzzles" / "preset_games"


@dataclass
class GameSession:
    graph_a: DiGraph
    graph_b: DiGraph
    config: RuleConfig = field(default_factory=RuleConfig)
    position: Position = field(default_factory=lambda: Position("A0", "B0"))
    history: List[Ply] = field(default_factory=list)
    jump_window: JumpWindow = field(default_factory=lambda: JumpWindow(history=[], limit=(2, 5)))


class TWGBGApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Two-Way Global Bisimulation Game")
        self.geometry("1400x860")
        self.minsize(1200, 720)
        self.theme: Theme = THEMES["Dark"]
        self.configure(background=self.theme.background)
        self.tutorial = TutorialManager()

        graph_a = load_json(str(DATA_DIR / "graph0.json"))
        graph_b = load_json(str(DATA_DIR / "graph1.json"))
        position = Position(graph_a.vertices()[0], graph_b.vertices()[0])
        self.session = GameSession(graph_a=graph_a, graph_b=graph_b, position=position)
        self.session.jump_window.limit = self.session.config.jump_cooldown

        self.alpha_engine = AlphaBetaEngine(tablebase=Tablebase(), learned_bias=LearnedBias())
        self.mcts_engine = MCTSEngine()
        self.hybrid_engine = HybridEngine()

        self.engine_mode = tk.StringVar(value="alphabeta")
        self.depth_var = tk.IntVar(value=4)
        self.time_var = tk.IntVar(value=900)
        self.mcts_iter_var = tk.IntVar(value=800)
        self.rollout_var = tk.IntVar(value=24)
        self.c_puct_var = tk.DoubleVar(value=1.4)
        self.seed_var = tk.IntVar(value=0)
        self.show_pv_var = tk.BooleanVar(value=True)
        self.show_heat_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="Ready")
        self.coach_text = tk.StringVar(value="Spoiler coach explanations appear here.")
        self.pending_move: Optional[Move] = None

        self.undo_stack: List[Ply] = []
        self.redo_stack: List[Ply] = []

        self._build_menu()
        self._build_layout()
        self._apply_theme(self.theme.name)
        self.update_analysis()
        self.refresh_hints([])

    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New random", command=self.new_random)
        file_menu.add_command(label="New path graphs", command=self.new_path)
        file_menu.add_separator()
        file_menu.add_command(label="Open session", command=self.load_session)
        file_menu.add_command(label="Save session", command=self.save_session)
        file_menu.add_separator()
        file_menu.add_command(label="Export board", command=self.export_board)
        file_menu.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    def _build_layout(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=4)
        ttk.Button(toolbar, text="Spoiler move (Space)", command=self.trigger_spoiler_move).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Undo", command=self.undo).pack(side="left")
        ttk.Button(toolbar, text="Redo", command=self.redo).pack(side="left")
        ttk.Button(toolbar, text="Replay", command=self.replay).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Load puzzle", command=self.load_puzzle).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Reset", command=self.reset_session).pack(side="left", padx=4)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=4)
        self.notebook = notebook

        play_tab = ttk.Frame(notebook)
        notebook.add(play_tab, text="Play")
        learn_tab = ttk.Frame(notebook)
        notebook.add(learn_tab, text="Learn")
        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="Analysis & Coach")
        experiments_tab = ttk.Frame(notebook)
        notebook.add(experiments_tab, text="Experiments")

        board_frame = ttk.Frame(play_tab)
        board_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.graph_view_a = GraphView(board_frame, self.theme)
        self.graph_view_b = GraphView(board_frame, self.theme)
        self.graph_view_a.pack(side="left", fill="both", expand=True, padx=4)
        self.graph_view_b.pack(side="left", fill="both", expand=True, padx=4)
        self.graph_view_a.set_on_click(lambda node: self._handle_node_click("A", node))
        self.graph_view_b.set_on_click(lambda node: self._handle_node_click("B", node))
        self.graph_view_a.set_graph(self.session.graph_a)
        self.graph_view_b.set_graph(self.session.graph_b)
        self.graph_view_a.set_current(self.session.position.A_curr)
        self.graph_view_b.set_current(self.session.position.B_curr)
        self._update_signatures()

        side_panel = ttk.Frame(play_tab)
        side_panel.pack(side="right", fill="y", padx=8, pady=8)
        self.rule_panel = RulePanel(side_panel, self.session.config, self._on_rule_change)
        self.rule_panel.pack(fill="x", pady=6)

        ai_frame = ttk.LabelFrame(side_panel, text="Spoiler AI")
        ai_frame.pack(fill="x", pady=6)
        ttk.Radiobutton(ai_frame, text="Iterative Alpha-Beta", variable=self.engine_mode, value="alphabeta").pack(anchor="w")
        ttk.Radiobutton(ai_frame, text="Monte-Carlo Tree Search", variable=self.engine_mode, value="mcts").pack(anchor="w")
        ttk.Radiobutton(ai_frame, text="Hybrid", variable=self.engine_mode, value="hybrid").pack(anchor="w")
        ttk.Label(ai_frame, text="Depth").pack(anchor="w")
        ttk.Spinbox(ai_frame, from_=2, to=8, textvariable=self.depth_var).pack(fill="x")
        ttk.Label(ai_frame, text="Time budget (ms)").pack(anchor="w")
        ttk.Spinbox(ai_frame, from_=100, to=5000, increment=100, textvariable=self.time_var).pack(fill="x")
        ttk.Label(ai_frame, text="MCTS iterations").pack(anchor="w")
        ttk.Spinbox(ai_frame, from_=100, to=5000, increment=50, textvariable=self.mcts_iter_var).pack(fill="x")
        ttk.Label(ai_frame, text="Rollout depth").pack(anchor="w")
        ttk.Spinbox(ai_frame, from_=8, to=128, textvariable=self.rollout_var).pack(fill="x")
        ttk.Label(ai_frame, text="c_puct").pack(anchor="w")
        ttk.Spinbox(ai_frame, from_=0.5, to=3.0, increment=0.1, textvariable=self.c_puct_var).pack(fill="x")
        ttk.Checkbutton(ai_frame, text="Show PV", variable=self.show_pv_var, command=self._refresh_overlays).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(ai_frame, text="Show heatmap", variable=self.show_heat_var, command=self._refresh_overlays).pack(anchor="w")

        ThemePanel(side_panel, self._apply_theme).pack(fill="x", pady=6)

        hints_frame = ttk.LabelFrame(play_tab, text="Hint chips")
        hints_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.hint_frame = ttk.Frame(hints_frame)
        self.hint_frame.pack(fill="x")

        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", padx=10, pady=(0, 6))

        # Learn tab
        tutorial_text = tk.Text(learn_tab, wrap="word", height=12, bg="#0f172a", fg="#f8fafc")
        tutorial_text.pack(fill="both", expand=True, padx=8, pady=8)
        tutorial_text.insert("1.0", self.tutorial.current().description)
        tutorial_text.config(state="disabled")
        nav = ttk.Frame(learn_tab)
        nav.pack(pady=4)
        ttk.Button(nav, text="Previous", command=lambda: self._tutorial_nav(-1, tutorial_text)).pack(side="left", padx=4)
        ttk.Button(nav, text="Next", command=lambda: self._tutorial_nav(1, tutorial_text)).pack(side="left", padx=4)
        ttk.Button(nav, text="Reset", command=lambda: self._tutorial_reset(tutorial_text)).pack(side="left", padx=4)

        # Analysis tab
        analysis_split = ttk.PanedWindow(analysis_tab, orient=tk.HORIZONTAL)
        analysis_split.pack(fill="both", expand=True, padx=8, pady=8)
        self.analysis_tree = ttk.Treeview(analysis_split, show="tree")
        analysis_split.add(self.analysis_tree)
        coach_frame = ttk.Frame(analysis_split)
        analysis_split.add(coach_frame)
        ttk.Label(coach_frame, text="Coach insights").pack(anchor="w")
        self.coach_box = tk.Text(coach_frame, height=18, wrap="word")
        self.coach_box.pack(fill="both", expand=True)
        self.coach_box.insert("1.0", self.coach_text.get())
        self.coach_box.config(state="disabled")

        # Experiments tab
        ttk.Label(
            experiments_tab,
            text="Run experiments via CLI:\npython -m twgbg.experiments.run --games 100 --mode hybrid --depth 4",
        ).pack(padx=20, pady=40)

        self.bind("<space>", lambda _: self.trigger_spoiler_move())
        self.bind("<Control-s>", lambda _: self.save_session())
        self.bind("<Control-o>", lambda _: self.load_session())
        self.bind("<Control-z>", lambda _: self.undo())
        self.bind("<Control-y>", lambda _: self.redo())

    # ------------------------------------------------------------------
    def _apply_theme(self, name: str) -> None:
        theme = THEMES.get(name, self.theme)
        self.theme = theme
        self.configure(background=theme.background)
        self.graph_view_a.apply_theme(theme)
        self.graph_view_b.apply_theme(theme)

    def _on_rule_change(self, config: RuleConfig) -> None:
        self.session.config = config
        self.session.jump_window.limit = config.jump_cooldown
        self.status_var.set("Rule configuration updated")

    def _update_signatures(self) -> None:
        sig_a = {node: "-" for node in self.session.graph_a.vertices()}
        sig_b = {node: "-" for node in self.session.graph_b.vertices()}
        try:
            sig_a = {node: str(sig) for node, sig in signature_partition(self.session.graph_a).items()}
            sig_b = {node: str(sig) for node, sig in signature_partition(self.session.graph_b).items()}
        finally:
            self.graph_view_a.set_signature_map(sig_a)
            self.graph_view_b.set_signature_map(sig_b)

    # ------------------------------------------------------------------
    def trigger_spoiler_move(self) -> None:
        if self.pending_move is not None:
            messagebox.showinfo("Pending move", "Complete the current Spoiler move before starting a new one.")
            return
        mode = self.engine_mode.get()
        config = self.session.config
        jump_window = self.session.jump_window
        position = self.session.position
        pv_nodes: List[str] = []
        heat: Dict[str, float] = {}
        if mode == "alphabeta":
            result: SearchResult = self.alpha_engine.search(
                self.session.graph_a,
                self.session.graph_b,
                position,
                config=config,
                jump_window=jump_window,
                max_depth=self.depth_var.get(),
                time_limit_ms=self.time_var.get(),
                seed=self.seed_var.get() or None,
            )
            move = result.move
            pv_nodes = [position.A_curr] + [mv.dest for mv in result.pv]
            self.status_var.set(
                f"αβ depth {result.depth} value {result.value:.2f} (nodes {result.stats.nodes}, cutoffs {result.stats.cutoffs})"
            )
            self._update_coach(result)
        elif mode == "mcts":
            self.mcts_engine.rollout_depth = self.rollout_var.get()
            move = self.mcts_engine.search(
                self.session.graph_a,
                self.session.graph_b,
                position,
                config=config,
                jump_window=jump_window,
                iterations=self.mcts_iter_var.get(),
                seed=self.seed_var.get() or None,
            )
            visits = self.mcts_engine.visit_counts
            if visits:
                max_visit = max(visits.values())
                for (side, dest), count in visits.items():
                    if side == "A":
                        heat[dest] = count / max_visit
                    else:
                        heat[dest] = count / max_visit
            self.status_var.set("MCTS search complete")
            self._coach_message("MCTS prioritised moves with minimal replies.")
        else:
            settings = HybridSettings(
                depth=self.depth_var.get(),
                iter_ms=self.time_var.get(),
                mcts_iterations=self.mcts_iter_var.get(),
                rollout_depth=self.rollout_var.get(),
            )
            move = self.hybrid_engine.choose_move(
                self.session.graph_a,
                self.session.graph_b,
                position,
                config=config,
                jump_window=jump_window,
                settings=settings,
                seed=self.seed_var.get() or None,
            )
            result = self.hybrid_engine.last_result
            if result:
                pv_nodes = [position.A_curr] + [mv.dest for mv in result.pv]
                self._update_coach(result)
            self.status_var.set("Hybrid controller combined search signals")
        if move is None:
            messagebox.showinfo("Game", "No legal Spoiler moves – Duplicator wins by survival!")
            return
        self.pending_move = move
        self._refresh_overlays(pv_nodes=pv_nodes, heat=heat, side=move.side)
        target = self.session.graph_b if move.side == "A" else self.session.graph_a
        replies = legal_responses(target, position, move, config)
        self.refresh_hints(replies)
        self.status_var.set(f"Spoiler plays {move.notation()} – select a reply on the other graph")
        if move.side == "A":
            self.graph_view_b.set_legal(replies)
        else:
            self.graph_view_a.set_legal(replies)

    def _refresh_overlays(
        self,
        *,
        pv_nodes: Optional[List[str]] = None,
        heat: Optional[Dict[str, float]] = None,
        side: Optional[str] = None,
    ) -> None:
        if not self.show_pv_var.get() or not pv_nodes:
            self.graph_view_a.set_pv([])
            self.graph_view_b.set_pv([])
        else:
            if side == "A":
                self.graph_view_a.set_pv(pv_nodes)
                self.graph_view_b.set_pv([])
            elif side == "B":
                self.graph_view_b.set_pv(pv_nodes)
                self.graph_view_a.set_pv([])
            else:
                self.graph_view_a.set_pv(pv_nodes)
                self.graph_view_b.set_pv(pv_nodes)
        if not self.show_heat_var.get() or not heat:
            self.graph_view_a.set_heatmap({})
            self.graph_view_b.set_heatmap({})
        else:
            if side == "A":
                self.graph_view_a.set_heatmap(heat)
            else:
                self.graph_view_b.set_heatmap(heat)

    def refresh_hints(self, replies: List[str]) -> None:
        for child in self.hint_frame.winfo_children():
            child.destroy()
        if not replies:
            ttk.Label(self.hint_frame, text="No legal replies – Spoiler threatens a loss!").pack(anchor="w")
            return
        ttk.Label(self.hint_frame, text="Legal replies:").pack(side="left", padx=(0, 6))
        for reply in replies:
            ttk.Button(self.hint_frame, text=reply, command=lambda r=reply: self._apply_reply(r)).pack(side="left", padx=2)

    def _handle_node_click(self, graph: str, node: str) -> None:
        if not self.pending_move:
            return
        if (self.pending_move.side == "A" and graph == "B") or (self.pending_move.side == "B" and graph == "A"):
            self._apply_reply(node)

    def _apply_reply(self, node: str) -> None:
        if not self.pending_move:
            return
        move = self.pending_move
        target_graph = self.session.graph_b if move.side == "A" else self.session.graph_a
        replies = legal_responses(target_graph, self.session.position, move, self.session.config)
        if node not in replies:
            messagebox.showerror("Illegal", "That node is not a valid reply under the current rules.")
            return
        new_pos, alive, info = step(
            self.session.graph_a,
            self.session.graph_b,
            self.session.position,
            move,
            node,
            config=self.session.config,
            jump_window=self.session.jump_window,
            round_number=len(self.session.history),
        )
        self.session.history.append(Ply(move, node))
        self.session.position = new_pos
        self.graph_view_a.set_current(new_pos.A_curr)
        self.graph_view_b.set_current(new_pos.B_curr)
        self.graph_view_a.set_legal([])
        self.graph_view_b.set_legal([])
        self.pending_move = None
        self._refresh_overlays()
        self.refresh_hints([])
        self.status_var.set(info)
        self._update_signatures()
        if not alive:
            messagebox.showinfo("Game", info)
        self.update_analysis()

    # ------------------------------------------------------------------
    def reset_session(self) -> None:
        self.session.history.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.pending_move = None
        self.session.position = Position(self.session.graph_a.vertices()[0], self.session.graph_b.vertices()[0])
        self.session.jump_window.history.clear()
        self.graph_view_a.set_current(self.session.position.A_curr)
        self.graph_view_b.set_current(self.session.position.B_curr)
        self.graph_view_a.set_legal([])
        self.graph_view_b.set_legal([])
        self._refresh_overlays()
        self.refresh_hints([])
        self.status_var.set("Session reset")

    def new_random(self) -> None:
        graph_a = random_digraph(8, 0.3, prefix="A")
        graph_b = random_digraph(8, 0.3, prefix="B")
        self._load_graph_pair(graph_a, graph_b)
        self.status_var.set("Random graphs generated")

    def new_path(self) -> None:
        graph_a = path_graph(6, prefix="A")
        graph_b = path_graph(6, prefix="B")
        self._load_graph_pair(graph_a, graph_b)
        self.status_var.set("Path graphs generated")

    def _load_graph_pair(self, graph_a: DiGraph, graph_b: DiGraph) -> None:
        pos = Position(graph_a.vertices()[0], graph_b.vertices()[0])
        self.session = GameSession(graph_a=graph_a, graph_b=graph_b, position=pos, config=self.session.config)
        self.session.jump_window.limit = self.session.config.jump_cooldown
        self.graph_view_a.set_graph(graph_a)
        self.graph_view_b.set_graph(graph_b)
        self.graph_view_a.set_current(pos.A_curr)
        self.graph_view_b.set_current(pos.B_curr)
        self._update_signatures()
        self.reset_session()

    def load_puzzle(self) -> None:
        puzzles = sorted(PUZZLE_DIR.glob("*.json"))
        if not puzzles:
            messagebox.showerror("Puzzles", "No puzzles found")
            return
        path = puzzles[0]
        with open(path, "r", encoding="utf8") as fh:
            data = json.load(fh)
        graph_a = load_json(str(PUZZLE_DIR.parent / data["A"]))
        graph_b = load_json(str(PUZZLE_DIR.parent / data["B"]))
        start_a = data["start"]["A"]
        start_b = data["start"]["B"]
        pos = Position(start_a, start_b)
        self.session = GameSession(graph_a=graph_a, graph_b=graph_b, position=pos, config=self.session.config)
        self.session.jump_window.limit = self.session.config.jump_cooldown
        self.graph_view_a.set_graph(graph_a)
        self.graph_view_b.set_graph(graph_b)
        self.graph_view_a.set_current(pos.A_curr)
        self.graph_view_b.set_current(pos.B_curr)
        self._update_signatures()
        self.reset_session()
        self.status_var.set(f"Loaded puzzle {path.name}")

    def save_session(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = {
            "config": {
                "allow_backward": self.session.config.allow_backward,
                "allow_jump": self.session.config.allow_jump,
                "force_same_graph": self.session.config.force_same_graph,
                "jump_cooldown": self.session.config.jump_cooldown,
                "round_limit": self.session.config.round_limit,
                "mirror_mode": self.session.config.mirror_mode,
            },
            "position": {"A": self.session.position.A_curr, "B": self.session.position.B_curr},
            "history": serialize(self.session.history),
        }
        with open(path, "w", encoding="utf8") as fh:
            json.dump(data, fh, indent=2)
        self.status_var.set(f"Session saved to {path}")

    def load_session(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf8") as fh:
            data = json.load(fh)
        self.session.config.allow_backward = data["config"].get("allow_backward", True)
        self.session.config.allow_jump = data["config"].get("allow_jump", True)
        self.session.config.force_same_graph = data["config"].get("force_same_graph")
        self.session.config.jump_cooldown = tuple(data["config"].get("jump_cooldown", (2, 5)))  # type: ignore
        self.session.config.round_limit = data["config"].get("round_limit")
        self.session.config.mirror_mode = data["config"].get("mirror_mode", False)
        self.session.position = Position(data["position"]["A"], data["position"]["B"])
        self.session.jump_window.limit = self.session.config.jump_cooldown
        self.graph_view_a.set_current(self.session.position.A_curr)
        self.graph_view_b.set_current(self.session.position.B_curr)
        self.status_var.set(f"Loaded session from {path}")

    def export_board(self) -> None:
        path = ask_export_file(".ps", [("PostScript", "*.ps")])
        if not path:
            return
        save_canvas_png(self.graph_view_a, path + "_A")
        save_canvas_png(self.graph_view_b, path + "_B")
        self.status_var.set(f"Exported board views to {path}")

    def update_analysis(self) -> None:
        self.analysis_tree.delete(*self.analysis_tree.get_children())
        root_a = self.analysis_tree.insert("", tk.END, text="Graph A signatures")
        for node, sig in signature_partition(self.session.graph_a).items():
            self.analysis_tree.insert(root_a, tk.END, text=f"{node}: {sig}")
        root_b = self.analysis_tree.insert("", tk.END, text="Graph B signatures")
        for node, sig in signature_partition(self.session.graph_b).items():
            self.analysis_tree.insert(root_b, tk.END, text=f"{node}: {sig}")

    def undo(self) -> None:
        if not self.session.history:
            return
        ply = self.session.history.pop()
        self.redo_stack.append(ply)
        if self.session.history:
            last = self.session.history[-1]
            self.session.position = Position(last.spoiler.dest if last.spoiler.side == "A" else last.duplicator, last.duplicator if last.spoiler.side == "A" else last.spoiler.dest)
        else:
            self.session.position = Position(self.session.graph_a.vertices()[0], self.session.graph_b.vertices()[0])
        self.graph_view_a.set_current(self.session.position.A_curr)
        self.graph_view_b.set_current(self.session.position.B_curr)
        self.status_var.set("Undo applied")

    def redo(self) -> None:
        if not self.redo_stack:
            return
        ply = self.redo_stack.pop()
        self.session.history.append(ply)
        self.session.position = Position(ply.spoiler.dest if ply.spoiler.side == "A" else ply.duplicator, ply.duplicator if ply.spoiler.side == "A" else ply.spoiler.dest)
        self.graph_view_a.set_current(self.session.position.A_curr)
        self.graph_view_b.set_current(self.session.position.B_curr)
        self.status_var.set("Redo applied")

    def replay(self) -> None:
        self.graph_view_a.set_legal([])
        self.graph_view_b.set_legal([])
        self.graph_view_a.set_pv([])
        self.graph_view_b.set_pv([])
        messagebox.showinfo("Replay", "Replay functionality is interactive – step through history with Undo/Redo.")

    def _tutorial_nav(self, direction: int, widget: tk.Text) -> None:
        stage = self.tutorial.next() if direction > 0 else self.tutorial.previous()
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", stage.description)
        widget.config(state="disabled")

    def _tutorial_reset(self, widget: tk.Text) -> None:
        stage = self.tutorial.reset()
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", stage.description)
        widget.config(state="disabled")

    def _update_coach(self, result: SearchResult) -> None:
        summary = [
            f"Principal variation depth {result.depth}",
            f"Nodes: {result.stats.nodes}, cutoffs: {result.stats.cutoffs}, qnodes: {result.stats.qnodes}",
            f"Search time: {format_duration(result.stats.duration_ms)}",
        ]
        if result.pv:
            summary.append("PV: " + " → ".join(mv.notation() for mv in result.pv))
        self._coach_message("\n".join(summary))

    def _coach_message(self, text: str) -> None:
        self.coach_box.config(state="normal")
        self.coach_box.delete("1.0", tk.END)
        self.coach_box.insert("1.0", text)
        self.coach_box.config(state="disabled")


def main() -> None:  # pragma: no cover
    app = TWGBGApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
