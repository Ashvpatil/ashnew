"""Canvas renderer for the bisimulation graphs with directed edge visuals."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from ..engine.game import Move, Position
from ..engine.graphs import DiGraph

NODE_R = 18
EDGE_COLOR = "#8aa"
EDGE_FORWARD = "#22c55e"
EDGE_BACKWARD = "#ef4444"
EDGE_JUMP = "#eab308"
ARROWSHAPE = (12, 16, 6)
EDGE_WIDTH = 2


def _trim_to_circle(x1: float, y1: float, x2: float, y2: float, r: float = NODE_R) -> Tuple[float, float, float, float]:
    """Trim a segment so it touches the circumference of circular nodes."""

    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return x1, y1, x2, y2
    trim = min(r / dist, 0.49)
    sx = x1 + dx * trim
    sy = y1 + dy * trim
    ex = x2 - dx * trim
    ey = y2 - dy * trim
    return sx, sy, ex, ey


def _curve_offset(u_key: str, v_key: str, mag: float = 18.0) -> float:
    """Deterministic perpendicular offset for bidirectional edges."""

    if u_key == v_key:
        return 0.0
    return mag if u_key < v_key else -mag


def _quad_curve_points(x1: float, y1: float, x2: float, y2: float, offset: float) -> List[float]:
    """Return control points for a quadratic bezier with perpendicular offset."""

    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return [x1, y1, x2, y2]
    nx = -dy / dist
    ny = dx / dist
    cx = mx + nx * offset
    cy = my + ny * offset
    return [x1, y1, cx, cy, x2, y2]


def _draw_directed_edge(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = EDGE_COLOR,
    width: float = EDGE_WIDTH,
    curved: bool = False,
    offset: float = 16.0,
    node_radius: float = NODE_R,
    arrowshape: Tuple[int, int, int] = ARROWSHAPE,
    tags: Tuple[str, ...] = (),
) -> int:
    """Draw a directed edge with optional curvature."""

    if curved:
        points = _quad_curve_points(x1, y1, x2, y2, offset)
        sx, sy, ex, ey = _trim_to_circle(points[0], points[1], points[-2], points[-1], node_radius)
        points[0], points[1] = sx, sy
        points[-2], points[-1] = ex, ey
        return canvas.create_line(
            *points,
            fill=color,
            width=width,
            smooth=True,
            splinesteps=24,
            arrow=tk.LAST,
            arrowshape=arrowshape,
            capstyle=tk.ROUND,
            tags=("edge",) + tags,
        )
    sx, sy, ex, ey = _trim_to_circle(x1, y1, x2, y2, node_radius)
    return canvas.create_line(
        sx,
        sy,
        ex,
        ey,
        fill=color,
        width=width,
        arrow=tk.LAST,
        arrowshape=arrowshape,
        capstyle=tk.ROUND,
        tags=("edge",) + tags,
    )


def _draw_self_loop(
    canvas: tk.Canvas,
    x: float,
    y: float,
    r: float = NODE_R,
    *,
    color: str = EDGE_COLOR,
    width: float = EDGE_WIDTH,
    arrowshape: Tuple[int, int, int] = ARROWSHAPE,
    tags: Tuple[str, ...] = (),
) -> int:
    """Draw a self loop as a small circular arc with arrow head."""

    loop_r = r * 1.6
    points = [
        x,
        y - r,
        x + loop_r,
        y - loop_r - r * 0.3,
        x,
        y - loop_r * 2.0,
        x - loop_r,
        y - loop_r - r * 0.3,
        x,
        y - r,
    ]
    return canvas.create_line(
        *points,
        fill=color,
        width=width,
        smooth=True,
        splinesteps=24,
        arrow=tk.LAST,
        arrowshape=arrowshape,
        capstyle=tk.ROUND,
        tags=("edge",) + tags,
    )


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
        self.show_hints = True
        self.show_pv = True
        self.layout: Dict[str, LayoutState] = {}
        self.node_items: Dict[int, Tuple[str, str]] = {}
        self.edge_colors: Dict[int, str] = {}
        self.on_node_click: Optional[Callable[[str, str], None]] = None
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-2>", self._start_pan)
        self.bind("<B2-Motion>", self._pan)
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Control-MouseWheel>", self._zoom)
        self.bind("<Button-4>", self._zoom)
        self.bind("<Button-5>", self._zoom)
        self.bind("<Button-1>", self._click)
        self.tag_bind("edge", "<Enter>", self._on_edge_enter)
        self.tag_bind("edge", "<Leave>", self._on_edge_leave)
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

    def set_overlays(self, *, hints: Optional[bool] = None, pv: Optional[bool] = None) -> None:
        """Toggle visibility of hint halos and principal variation overlays."""

        if hints is not None:
            self.show_hints = hints
        if pv is not None:
            self.show_pv = pv
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
        delta: float
        if getattr(event, "delta", 0):
            delta = 1.1 if event.delta > 0 else 0.9
        elif getattr(event, "num", None) in (4, 5):
            delta = 1.1 if event.num == 4 else 0.9
        else:
            return
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
        self.edge_colors.clear()
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
            raw_hints = self.hints_a if side == "A" else self.hints_b
            hints = set(raw_hints if self.show_hints else [])
            current = self.position.A_curr if side == "A" else self.position.B_curr
            forward_targets = set(graph.succ.get(current, set())) if current else set()
            backward_sources = set(graph.pred.get(current, set())) if current else set()
            jump_targets = {h for h in hints if h not in forward_targets and h not in backward_sources}
            width_scale = max(0.6, min(1.6, self.scale_factor))
            edge_width = EDGE_WIDTH * width_scale
            node_radius = NODE_R * self.scale_factor
            arrowshape = tuple(max(4, int(s * width_scale)) for s in ARROWSHAPE)

            def project(px: float, py: float) -> Tuple[float, float]:
                return (
                    cx + (px + offset_x) * self.scale_factor,
                    cy + (py + offset_y) * self.scale_factor,
                )

            # Draw edges first
            for u, vs in graph.succ.items():
                if u not in layout.positions:
                    continue
                for v in vs:
                    if v not in layout.positions:
                        continue
                    x1_raw, y1_raw = layout.positions[u]
                    x2_raw, y2_raw = layout.positions[v]
                    x1, y1 = project(x1_raw, y1_raw)
                    x2, y2 = project(x2_raw, y2_raw)
                    tags = (f"edge:{side}:{u}->{v}",)
                    color = EDGE_COLOR
                    if current:
                        if u == current and v in forward_targets:
                            color = EDGE_FORWARD
                        elif v == current and u in backward_sources:
                            color = EDGE_BACKWARD
                    if v in jump_targets and u == current:
                        color = EDGE_JUMP
                    if u == v:
                        item = _draw_self_loop(
                            self,
                            x1,
                            y1,
                            r=node_radius,
                            color=color,
                            width=edge_width,
                            arrowshape=arrowshape,
                            tags=tags,
                        )
                    else:
                        reverse = u in graph.pred.get(v, set())
                        offset = _curve_offset(u, v, mag=18.0) * self.scale_factor
                        item = _draw_directed_edge(
                            self,
                            x1,
                            y1,
                            x2,
                            y2,
                            color=color,
                            width=edge_width,
                            curved=reverse,
                            offset=offset,
                            node_radius=node_radius,
                            arrowshape=arrowshape,
                            tags=tags,
                        )
                    self.edge_colors[item] = color
            self.tag_lower("edge")

            pv_nodes = {(m.side, m.dest) for m in self.pv} if self.show_pv else set()
            for node, (x, y) in layout.positions.items():
                px, py = project(x, y)
                r = node_radius
                fill = palette[side]
                if (side, node) in pv_nodes:
                    self.create_oval(px - r - 4, py - r - 4, px + r + 4, py + r + 4, outline="#9bf6ff", width=3)
                if node == current:
                    self.create_oval(px - r - 6, py - r - 6, px + r + 6, py + r + 6, outline="#3a86ff", width=4)
                if node in hints:
                    self.create_oval(
                        px - r - 10,
                        py - r - 10,
                        px + r + 10,
                        py + r + 10,
                        outline="#80ed99",
                        width=2,
                        dash=(4, 2),
                    )
                intensity = self._heat_intensity(side, node)
                color = self._blend(fill, "#ffffff", intensity)
                item = self.create_oval(px - r, py - r, px + r, py + r, fill=color, outline="#000")
                self.node_items[item] = (side, node)
                self.create_text(px, py, text=node, fill="#fff", font=("Helvetica", int(10 * max(0.6, self.scale_factor))))

    def _on_edge_enter(self, event: tk.Event) -> None:
        iid = event.widget.find_withtag("current")
        if not iid:
            return
        item_id = iid[0]
        base = self.edge_colors.get(item_id, EDGE_COLOR)
        highlight = self._blend(base, "#ddeeff", 0.35)
        event.widget.itemconfigure(item_id, fill=highlight)

    def _on_edge_leave(self, event: tk.Event) -> None:
        iid = event.widget.find_withtag("current")
        if not iid:
            return
        item_id = iid[0]
        base = self.edge_colors.get(item_id, EDGE_COLOR)
        event.widget.itemconfigure(item_id, fill=base)

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
