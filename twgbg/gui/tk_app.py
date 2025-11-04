"""Tkinter front-end for the Two-Way Global Bisimulation Game."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..engine.graphs import DiGraph
from ..engine.game import Move, Position
from ..ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from ..ai.mcts import MCTSSpoiler, MCTSConfig
from ..ai.learning import TabularValue
from ..analysis.bisim import approximate_bisimulation
from ..analysis.witness import generate_witness

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DATA = Path(__file__).resolve().parent.parent / "data"


class GraphCanvas(tk.Canvas):
    def __init__(self, master: tk.Widget, name: str, graph_id: str, status_callback, click_callback=None, **kwargs) -> None:
        super().__init__(master, background="white", width=400, height=400, **kwargs)
        self.name = name
        self.graph_id = graph_id
        self.status_callback = status_callback
        self.click_callback = click_callback
        self.positions: Dict[str, Tuple[float, float]] = {}
        self.node_items: Dict[int, str] = {}
        self.bind("<Motion>", self.on_motion)
        self.bind("<Button-1>", self.on_click)

    def draw_graph(
        self,
        graph: DiGraph,
        current: str,
        hints: List[str],
        pv_edges: List[Tuple[str, str]],
        heat: Dict[str, int],
    ) -> None:
        self.delete("all")
        self.node_items.clear()
        if len(graph) == 0:
            return
        self.positions = force_layout(graph, width=float(self.winfo_width()), height=float(self.winfo_height()))
        max_heat = max(heat.values(), default=0)
        for src, tgt in graph.edges():
            src_pos = self.positions[src]
            tgt_pos = self.positions[tgt]
            width = 2
            color = "#999"
            if (src, tgt) in pv_edges:
                width = 4
                color = "#2ecc71"
            self.create_line(src_pos[0], src_pos[1], tgt_pos[0], tgt_pos[1], arrow=tk.LAST, width=width, fill=color)
        for node, (x, y) in self.positions.items():
            radius = 14
            fill = "#4c78a8"
            if node == current:
                fill = "#1f77b4"
            if node in hints:
                fill = "#2ecc71"
            if max_heat:
                intensity = heat.get(node, 0) / max_heat
                if intensity:
                    fill = _blend(fill, "#ff6f69", intensity)
            item = self.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="black", width=2)
            text = self.create_text(x, y, text=node, fill="white")
            self.node_items[item] = node
            self.node_items[text] = node

    def on_motion(self, event: tk.Event) -> None:
        item = self.find_withtag(tk.CURRENT)
        if item:
            node = self.node_items.get(item[0])
            if node:
                self.status_callback(f"{self.name}: {node}")
                return
        self.status_callback("")

    def on_click(self, event: tk.Event) -> None:
        if not self.click_callback:
            return
        item = self.find_closest(event.x, event.y)
        node = self.node_items.get(item[0]) if item else None
        if node:
            self.click_callback(self.graph_id, node)


def force_layout(graph: DiGraph, width: float, height: float) -> Dict[str, Tuple[float, float]]:
    if width <= 0 or height <= 0:
        width = height = 400
    rng = random.Random(42)
    positions = {node: (rng.random() * width, rng.random() * height) for node in graph.nodes()}
    for _ in range(200):
        forces = {node: [0.0, 0.0] for node in graph.nodes()}
        for u in graph.nodes():
            for v in graph.nodes():
                if u == v:
                    continue
                dx = positions[u][0] - positions[v][0]
                dy = positions[u][1] - positions[v][1]
                dist_sq = dx * dx + dy * dy + 0.01
                rep = 1000 / dist_sq
                forces[u][0] += dx / math.sqrt(dist_sq) * rep
                forces[u][1] += dy / math.sqrt(dist_sq) * rep
        for u, vs in graph.successors.items():
            for v in vs:
                dx = positions[v][0] - positions[u][0]
                dy = positions[v][1] - positions[u][1]
                dist = math.sqrt(dx * dx + dy * dy) + 0.01
                attr = dist * 0.05
                forces[u][0] += dx / dist * attr
                forces[u][1] += dy / dist * attr
                forces[v][0] -= dx / dist * attr
                forces[v][1] -= dy / dist * attr
        for node, (fx, fy) in forces.items():
            x, y = positions[node]
            x = min(max(x + fx * 0.01, 40), width - 40)
            y = min(max(y + fy * 0.01, 40), height - 40)
            positions[node] = (x, y)
    return positions


def _blend(base: str, overlay: str, t: float) -> str:
    def to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(ch * 2 for ch in hex_color)
        return tuple(int(hex_color[i : i + 2], 16) for i in range(0, 6, 2))

    def to_hex(rgb: Tuple[int, int, int]) -> str:
        return "#" + "".join(f"{c:02x}" for c in rgb)

    r1, g1, b1 = to_rgb(base)
    r2, g2, b2 = to_rgb(overlay)
    r = int((1 - t) * r1 + t * r2)
    g = int((1 - t) * g1 + t * g2)
    b = int((1 - t) * b1 + t * b2)
    return to_hex((r, g, b))


class GameApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Two-Way Global Bisimulation Game")
        self.geometry("1100x720")
        self.status_text = tk.StringVar(value="Ready")
        self.value_fn = TabularValue()
        self.alpha_beta = AlphaBetaSpoiler(SearchConfig(max_depth=4, time_budget=1.5), value_fn=self.value_fn)
        self.mcts = MCTSSpoiler(MCTSConfig(iterations=600, time_budget=2.0), value_fn=self.value_fn)
        self.position = self.load_default_position()
        self.history: List[Position] = [self.position.clone()]
        self.redo_stack: List[Position] = []
        self.current_ai = "alphabeta"
        self.hints: List[str] = []
        self.pv_edges: List[Tuple[str, str]] = []
        self.heat_map: Dict[str, int] = {}
        self.pending_move: Optional[Tuple[Move, List[Move]]] = None
        self.allow_backward_var = tk.BooleanVar(value=self.position.allow_backward)
        self.allow_jump_var = tk.BooleanVar(value=self.position.allow_jump)
        self.force_graph_var = tk.StringVar(value="None")
        self.ai_mode_var = tk.StringVar(value="alphabeta")
        self.depth_var = tk.IntVar(value=self.alpha_beta.config.max_depth)
        self.iter_var = tk.IntVar(value=int(self.alpha_beta.config.time_budget * 1000))
        self.rollouts_var = tk.IntVar(value=self.mcts.config.iterations)
        self.playout_var = tk.IntVar(value=self.mcts.config.rollout_depth)
        self.cpuct_var = tk.DoubleVar(value=self.mcts.config.c_puct)
        self.create_widgets()
        self.bind_shortcuts()
        self.refresh()

    # ------------------------------------------------------------------
    def load_default_position(self) -> Position:
        sample_path = DATA / "sample_graphs" / "chain.json"
        if sample_path.exists():
            with open(sample_path, "r", encoding="utf8") as fh:
                payload = json.load(fh)
            graph = DiGraph.from_dict(payload)
            return Position(graph, graph.copy(), next(iter(graph.nodes())), next(iter(graph.nodes())))
        g1 = DiGraph.random_graph(5, 0.4, seed=1)
        g2 = DiGraph.random_graph(5, 0.5, seed=2)
        return Position(g1, g2, next(iter(g1.nodes())), next(iter(g2.nodes())))

    def create_widgets(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        play_frame = ttk.Frame(notebook)
        notebook.add(play_frame, text="Play")
        analysis_frame = ttk.Frame(notebook)
        notebook.add(analysis_frame, text="Analysis & Coach")
        rules_frame = ttk.Frame(notebook)
        notebook.add(rules_frame, text="Rules")

        self.canvas_a = GraphCanvas(play_frame, "Graph A", "A", self.set_status, self.on_canvas_click)
        self.canvas_b = GraphCanvas(play_frame, "Graph B", "B", self.set_status, self.on_canvas_click)
        self.canvas_a.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.canvas_b.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        play_frame.columnconfigure(0, weight=1)
        play_frame.columnconfigure(1, weight=1)
        play_frame.rowconfigure(0, weight=1)

        controls = ttk.Frame(play_frame)
        controls.grid(row=1, column=0, columnspan=2, sticky="ew")
        for idx in range(5):
            controls.columnconfigure(idx, weight=1)

        ttk.Button(controls, text="New Random", command=self.new_random).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Path Graphs", command=self.load_path).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Demo", command=self.demo_play).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Spoiler Move", command=self.spoiler_move).grid(row=0, column=3, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Hint", command=self.show_hint).grid(row=0, column=4, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="PV Preview", command=self.toggle_pv).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Explain", command=self.explain).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Replay", command=self.replay).grid(row=1, column=2, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Undo", command=self.undo).grid(row=1, column=3, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Redo", command=self.redo).grid(row=1, column=4, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Save", command=self.save_state).grid(row=2, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Load", command=self.load_state).grid(row=2, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls, text="Heatmap", command=self.toggle_heat).grid(row=2, column=2, padx=4, pady=4, sticky="ew")

        settings = ttk.Labelframe(play_frame, text="Settings")
        settings.grid(row=0, column=2, rowspan=2, sticky="ns")
        ttk.Checkbutton(settings, text="Allow backward", variable=self.allow_backward_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Checkbutton(settings, text="Allow jump", variable=self.allow_jump_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Label(settings, text="Force same graph").pack(anchor="w", padx=4)
        force_combo = ttk.Combobox(settings, values=["None", "A", "B"], textvariable=self.force_graph_var, state="readonly")
        force_combo.pack(anchor="w", padx=4, pady=2)
        force_combo.bind("<<ComboboxSelected>>", lambda _: self.apply_settings())
        ttk.Label(settings, text="Engine").pack(anchor="w", padx=4, pady=2)
        engine_combo = ttk.Combobox(settings, values=["alphabeta", "mcts"], textvariable=self.ai_mode_var, state="readonly")
        engine_combo.pack(anchor="w", padx=4, pady=2)
        engine_combo.bind("<<ComboboxSelected>>", lambda _: self.apply_settings())
        ttk.Label(settings, text="Depth").pack(anchor="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=1, to=10, textvariable=self.depth_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Label(settings, text="Iter ms").pack(anchor="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=100, to=5000, increment=100, textvariable=self.iter_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Label(settings, text="Rollouts").pack(anchor="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=100, to=5000, increment=100, textvariable=self.rollouts_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Label(settings, text="Playout depth").pack(anchor="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=10, to=100, increment=5, textvariable=self.playout_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Label(settings, text="c_puct").pack(anchor="w", padx=4, pady=2)
        ttk.Spinbox(settings, from_=0.5, to=3.0, increment=0.1, textvariable=self.cpuct_var, command=self.apply_settings).pack(anchor="w", padx=4, pady=2)
        ttk.Button(settings, text="Apply", command=self.apply_settings).pack(anchor="ew", padx=4, pady=4)

        self.status_bar = ttk.Label(self, textvariable=self.status_text, relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Analysis tab
        self.analysis_text = tk.Text(analysis_frame, wrap="word")
        self.analysis_text.pack(fill=tk.BOTH, expand=True)

        # Rules tab
        rules = tk.Text(rules_frame, wrap="word")
        rules.insert(tk.END, "Two-way bisimulation game rules\n\n")
        rules.insert(tk.END, "Spoiler chooses graph and move type, Duplicator matches in the other graph. Forward/backward/jump moves available depending on settings. Duplicator loses when unable to match a move; infinite play favours Duplicator.")
        rules.config(state=tk.DISABLED)
        rules.pack(fill=tk.BOTH, expand=True)

    def bind_shortcuts(self) -> None:
        self.bind("<space>", lambda _: self.spoiler_move())
        self.bind("h", lambda _: self.show_hint())
        self.bind("p", lambda _: self.toggle_pv())
        self.bind("r", lambda _: self.replay())
        self.bind("<Control-s>", lambda _: self.save_state())
        self.bind("<Control-o>", lambda _: self.load_state())
        self.bind("<Control-z>", lambda _: self.undo())
        self.bind("<Control-y>", lambda _: self.redo())

    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        if text:
            self.status_text.set(text)
        else:
            self.status_text.set("Ready")

    def refresh(self) -> None:
        hints_a = [h for h in self.hints if h in self.position.graph_a.successors]
        hints_b = [h for h in self.hints if h in self.position.graph_b.successors]
        heat_a = {node: val for (graph, node), val in self.heat_map.items() if graph == "A"}
        heat_b = {node: val for (graph, node), val in self.heat_map.items() if graph == "B"}
        self.canvas_a.draw_graph(self.position.graph_a, self.position.node_a, hints_a, self.pv_edges, heat_a)
        self.canvas_b.draw_graph(self.position.graph_b, self.position.node_b, hints_b, self.pv_edges, heat_b)
        self.update_analysis()

    def update_analysis(self) -> None:
        bisim = approximate_bisimulation(self.position.graph_a, self.position.graph_b)
        self.analysis_text.delete("1.0", tk.END)
        self.analysis_text.insert(tk.END, "Signature pairs:\n")
        for sig, pairs in bisim.items():
            self.analysis_text.insert(tk.END, f"{sig}: {pairs}\n")
        witness = generate_witness(self.position)
        if witness:
            self.analysis_text.insert(tk.END, "\nWitness:\n")
            self.analysis_text.insert(tk.END, witness.describe())

    def push_history(self) -> None:
        self.history.append(self.position.clone())
        self.redo_stack.clear()

    def apply_settings(self) -> None:
        self.position.allow_backward = self.allow_backward_var.get()
        self.position.allow_jump = self.allow_jump_var.get()
        force_value = self.force_graph_var.get()
        self.position.force_same_graph = None if force_value == "None" else force_value
        self.current_ai = self.ai_mode_var.get()
        depth = max(1, self.depth_var.get())
        self.alpha_beta.config.max_depth = depth
        self.alpha_beta.config.time_budget = max(0.1, self.iter_var.get() / 1000)
        self.mcts.config.iterations = max(100, self.rollouts_var.get())
        self.mcts.config.rollout_depth = max(5, self.playout_var.get())
        self.mcts.config.c_puct = float(self.cpuct_var.get())
        self.pending_move = None
        if self.history:
            self.history[-1] = self.position.clone()
        self.refresh()

    def new_random(self) -> None:
        g1 = DiGraph.random_graph(6, 0.4, seed=random.randint(0, 9999))
        g2 = DiGraph.random_graph(6, 0.4, seed=random.randint(0, 9999))
        self.position = Position(g1, g2, next(iter(g1.nodes())), next(iter(g2.nodes())))
        self.history = [self.position.clone()]
        self.redo_stack.clear()
        self.apply_settings()

    def on_canvas_click(self, graph_id: str, node: str) -> None:
        if not self.pending_move:
            return
        move, replies = self.pending_move
        expected = "B" if move.graph == "A" else "A"
        if graph_id != expected:
            self.set_status(f"Respond in graph {expected}")
            return
        for reply in replies:
            if reply.target == node:
                self.position = self.position.step(move, reply)
                self.pending_move = None
                self.hints = []
                self.pv_edges = []
                self.push_history()
                self.refresh()
                return
        self.set_status("Illegal reply")

    def load_path(self) -> None:
        graph = DiGraph()
        for idx in range(5):
            node = f"p{idx}"
            graph.add_node(node)
            if idx:
                graph.add_edge(f"p{idx-1}", node)
        self.position = Position(graph, graph.copy(), "p0", "p0")
        self.history = [self.position.clone()]
        self.apply_settings()

    def demo_play(self) -> None:
        for _ in range(3):
            if not self.spoiler_move():
                break

    def spoiler_move(self) -> bool:
        if self.pending_move:
            self.set_status("Resolve current round first")
            return False
        ai = self.alpha_beta if self.current_ai == "alphabeta" else self.mcts
        if isinstance(ai, AlphaBetaSpoiler):
            info = ai.choose_move(self.position)
            move = info.best_move
            self.pv_edges = [(mv.source, mv.target) for mv in info.principal_variation]
            self.hints = [mv.target for mv in info.principal_variation[:3]]
            self.set_status(f"PV depth {info.depth_reached} value {info.value:.2f}")
            self.heat_map = {}
        else:
            move, heat = ai.choose_move(self.position)
            self.heat_map = {(graph, node): val for (graph, node), val in heat.items()}
        if move is None:
            messagebox.showinfo("Result", "Duplicator holds! No spoiler moves.")
            return False
        responses = self.position.legal_responses(move)
        if not responses:
            messagebox.showinfo("Result", f"Spoiler wins with {move.describe()}")
            return False
        self.pending_move = (move, responses)
        self.hints = [reply.target for reply in responses]
        target_graph = "B" if move.graph == "A" else "A"
        self.set_status(f"Select response in graph {target_graph}")
        self.refresh()
        return True

    def show_hint(self) -> None:
        if self.pending_move:
            self.set_status("Resolve current round first")
            return
        info = self.alpha_beta.choose_move(self.position)
        if info.best_move:
            self.hints = [info.best_move.target]
            self.set_status(f"Hint: {info.best_move.describe()}")
            self.refresh()

    def toggle_pv(self) -> None:
        if self.pending_move:
            self.set_status("Resolve current round first")
            return
        if self.pv_edges:
            self.pv_edges.clear()
        else:
            info = self.alpha_beta.choose_move(self.position)
            self.pv_edges = [(mv.source, mv.target) for mv in info.principal_variation]
        self.refresh()

    def explain(self) -> None:
        if self.pending_move:
            self.set_status("Resolve current round first")
            return
        info = self.alpha_beta.choose_move(self.position)
        if not info.best_move:
            messagebox.showinfo("Explain", "No forced moves available.")
            return
        text = [f"Chosen move: {info.best_move.describe()}"]
        text.append(f"Depth reached: {info.depth_reached}")
        text.append(f"Heuristic value: {info.value:.2f}")
        if info.alt_moves:
            text.append("Alternatives:")
            for move, value in info.alt_moves:
                text.append(f"  {move.describe()} -> {value:.2f}")
        messagebox.showinfo("Coach", "\n".join(text))

    def replay(self) -> None:
        if len(self.history) <= 1:
            return
        self.position = self.history[0].clone()
        self.pending_move = None
        for past in self.history[1:]:
            self.position = past
            self.refresh()
            self.update()
            self.after(200)

    def undo(self) -> None:
        if len(self.history) <= 1:
            return
        state = self.history.pop()
        self.redo_stack.append(state)
        self.position = self.history[-1].clone()
        self.pending_move = None
        self.refresh()

    def redo(self) -> None:
        if not self.redo_stack:
            return
        state = self.redo_stack.pop()
        self.history.append(state.clone())
        self.position = state.clone()
        self.pending_move = None
        self.refresh()

    def save_state(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        payload = {
            "graph_a": self.position.graph_a.to_dict(),
            "graph_b": self.position.graph_b.to_dict(),
            "node_a": self.position.node_a,
            "node_b": self.position.node_b,
        }
        with open(path, "w", encoding="utf8") as fh:
            json.dump(payload, fh, indent=2)

    def load_state(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf8") as fh:
            payload = json.load(fh)
        graph_a = DiGraph.from_dict(payload["graph_a"])
        graph_b = DiGraph.from_dict(payload["graph_b"])
        self.position = Position(graph_a, graph_b, payload["node_a"], payload["node_b"])
        self.history = [self.position.clone()]
        self.apply_settings()

    def toggle_heat(self) -> None:
        if self.heat_map:
            self.heat_map = {}
        else:
            _, heat = self.mcts.choose_move(self.position)
            self.heat_map = heat
        self.refresh()


def main() -> None:
    app = GameApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
