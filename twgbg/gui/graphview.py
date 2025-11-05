"""Canvas renderer for the bisimulation graphs."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from ..engine.game import Move, Position
from ..engine.graphs import DiGraph


@dataclass
class LayoutState:
    positions: Dict[str, Tuple[float, float]]
    velocities: Dict[str, Tuple[float, float]]


class GraphCanvas(tk.Canvas):
    """Interactive canvas supporting zoom, pan and overlays."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(master, background="#111", highlightthickness=0, **kwargs)
        self.scale_factor = 1.0
        self.offset = (0.0, 0.0)
        self.graph_a: Optional[DiGraph] = None
        self.graph_b: Optional[DiGraph] = None
        self.position = Position(None, None)
        self.hints_a: List[str] = []
        self.hints_b: List[str] = []
        self.pv: List[Move] = []
        self.heatmap: Dict[Tuple[str, str], int] = {}
        self.layout: Dict[str, LayoutState] = {}
        self.node_items: Dict[int, Tuple[str, str]] = {}
        self.on_node_click: Optional[Callable[[str, str], None]] = None
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-2>", self._start_pan)
        self.bind("<B2-Motion>", self._pan)
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Control-MouseWheel>", self._zoom)
        self.bind("<Button-1>", self._click)
        self._pan_start: Optional[Tuple[float, float]] = None

    def set_graphs(
        self,
        graph_a: DiGraph,
        graph_b: DiGraph,
        position: Position,
    ) -> None:
        self.graph_a = graph_a
        self.graph_b = graph_b
        self.position = position
        self.layout["A"] = self._compute_layout(graph_a)
        self.layout["B"] = self._compute_layout(graph_b)
        self.redraw()

    def update_state(
        self,
        position: Position,
        hints_a: Iterable[str],
        hints_b: Iterable[str],
        pv: Iterable[Move],
        heatmap: Dict[Tuple[str, str], int],
    ) -> None:
        self.position = position
        self.hints_a = list(hints_a)
        self.hints_b = list(hints_b)
        self.pv = list(pv)
        self.heatmap = heatmap
        self.redraw()

    def set_click_callback(self, callback: Callable[[str, str], None]) -> None:
        self.on_node_click = callback

    # Interaction helpers
    def _start_pan(self, event: tk.Event) -> None:
        self._pan_start = (event.x, event.y)

    def _pan(self, event: tk.Event) -> None:
        if self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self.offset = (self.offset[0] + dx, self.offset[1] + dy)
        self._pan_start = (event.x, event.y)
        self.redraw()

    def _zoom(self, event: tk.Event) -> None:
        delta = 1.1 if event.delta > 0 else 0.9
        self.scale_factor *= delta
        self.scale_factor = max(0.4, min(2.5, self.scale_factor))
        self.redraw()

    def _click(self, event: tk.Event) -> None:
        item = self.find_closest(event.x, event.y)
        if not item:
            return
        node = self.node_items.get(item[0])
        if node and self.on_node_click:
            self.on_node_click(*node)

    # Layout + drawing
    def _compute_layout(self, graph: DiGraph) -> LayoutState:
        positions: Dict[str, Tuple[float, float]] = {}
        velocities: Dict[str, Tuple[float, float]] = {}
        n = max(len(graph.succ), 1)
        radius = 160
        for i, node in enumerate(sorted(graph.succ)):
            angle = 2 * math.pi * i / n
            positions[node] = (math.cos(angle) * radius, math.sin(angle) * radius)
            velocities[node] = (0.0, 0.0)
        for _ in range(15):
            forces = {v: [0.0, 0.0] for v in positions}
            for u in positions:
                for v in positions:
                    if u == v:
                        continue
                    dx = positions[u][0] - positions[v][0]
                    dy = positions[u][1] - positions[v][1]
                    dist_sq = dx * dx + dy * dy + 0.01
                    rep = 20000 / dist_sq
                    forces[u][0] += dx * rep
                    forces[u][1] += dy * rep
            for u, vs in graph.succ.items():
                for v in vs:
                    if v not in positions:
                        continue
                    dx = positions[v][0] - positions[u][0]
                    dy = positions[v][1] - positions[u][1]
                    attr = 0.01
                    forces[u][0] += dx * attr
                    forces[u][1] += dy * attr
                    forces[v][0] -= dx * attr
                    forces[v][1] -= dy * attr
            for node in positions:
                vx, vy = velocities[node]
                vx = (vx + forces[node][0]) * 0.85
                vy = (vy + forces[node][1]) * 0.85
                x, y = positions[node]
                positions[node] = (x + vx * 0.01, y + vy * 0.01)
                velocities[node] = (vx, vy)
        return LayoutState(positions, velocities)

    def redraw(self) -> None:
        self.delete("all")
        self.node_items.clear()
        if not self.graph_a or not self.graph_b:
            return
        palette = {"A": "#4cc9f0", "B": "#f07167"}
        width = self.winfo_width() or 800
        height = self.winfo_height() or 600
        mid_x = width / 2
        mid_y = height / 2
        offset_x = self.offset[0]
        offset_y = self.offset[1]
        for side, graph, layout in (("A", self.graph_a, self.layout.get("A")), ("B", self.graph_b, self.layout.get("B"))):
            if layout is None:
                continue
            cx = mid_x / 2 if side == "A" else mid_x + mid_x / 2
            cy = mid_y
            for u, vs in graph.succ.items():
                for v in vs:
                    x1, y1 = layout.positions[u]
                    x2, y2 = layout.positions[v]
                    x1 = cx + (x1 + offset_x) * self.scale_factor
                    y1 = cy + (y1 + offset_y) * self.scale_factor
                    x2 = cx + (x2 + offset_x) * self.scale_factor
                    y2 = cy + (y2 + offset_y) * self.scale_factor
                    self.create_line(x1, y1, x2, y2, fill="#444", width=2, arrow=tk.LAST, smooth=True)
            hints = self.hints_a if side == "A" else self.hints_b
            current = self.position.A_curr if side == "A" else self.position.B_curr
            pv_nodes = {(m.side, m.dest) for m in self.pv}
            for node, (x, y) in layout.positions.items():
                px = cx + (x + offset_x) * self.scale_factor
                py = cy + (y + offset_y) * self.scale_factor
                r = 18 * self.scale_factor
                fill = palette[side]
                if (side, node) in pv_nodes:
                    self.create_oval(px - r - 4, py - r - 4, px + r + 4, py + r + 4, outline="#9bf6ff", width=3)
                if node == current:
                    self.create_oval(px - r - 6, py - r - 6, px + r + 6, py + r + 6, outline="#3a86ff", width=4)
                if node in hints:
                    self.create_oval(px - r - 10, py - r - 10, px + r + 10, py + r + 10, outline="#80ed99", width=2, dash=(4, 2))
                intensity = self._heat_intensity(side, node)
                color = self._blend(fill, "#ffffff", intensity)
                item = self.create_oval(px - r, py - r, px + r, py + r, fill=color, outline="#000")
                self.node_items[item] = (side, node)
                self.create_text(px, py, text=node, fill="#fff", font=("Helvetica", int(10 * self.scale_factor)))

    def _heat_intensity(self, side: str, node: str) -> float:
        if not self.heatmap:
            return 0.0
        total = max(self.heatmap.values())
        if total <= 0:
            return 0.0
        return self.heatmap.get((side, node), 0) / total

    @staticmethod
    def _blend(color1: str, color2: str, t: float) -> str:
        def to_rgb(hex_color: str) -> Tuple[int, int, int]:
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        def to_hex(rgb: Tuple[int, int, int]) -> str:
            return "#" + "".join(f"{c:02x}" for c in rgb)

        r1, g1, b1 = to_rgb(color1)
        r2, g2, b2 = to_rgb(color2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return to_hex((r, g, b))
