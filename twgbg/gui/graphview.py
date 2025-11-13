"""Canvas renderer for the bisimulation graphs with rich visuals."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from ..engine.game import Move, Position
from ..engine.graphs import DiGraph

# Geometry and palette constants -------------------------------------------------
NODE_R = 18
EDGE_WIDTH = 2
ARROWSHAPE = (12, 16, 6)

EDGE_COLOR = "#8aa"
EDGE_FORWARD = "#22c55e"
EDGE_BACKWARD = "#ef4444"
EDGE_JUMP = "#eab308"

COL_BG_TOP = "#0b1020"
COL_BG_BOTTOM = "#0e172a"
COL_BG_VIGNETTE = "#05070e"
COL_EDGE = "#7e8ca0"
COL_EDGE_HOVER = "#b7c2d1"
COL_NODE_CURR = "#60a5fa"
COL_HINT_HALO = "#8bffb0"
COL_PV_EDGE = "#22c55e"
COL_HEAT_LOW = "#1f2937"
COL_HEAT_HIGH = "#60a5fa"
COL_LABEL = "#f9fafb"
COL_LABEL_SHADOW = "#000000"
COL_NODE_A = "#38bdf8"
COL_NODE_B = "#f472b6"

PULSE_INTERVAL_MS = 33
PULSE_SPEED = 0.07
PV_SPEED = 2.5


# Helper utilities ----------------------------------------------------------------
def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_hex(color_a: str, color_b: str, t: float) -> str:
    """Blend two hex colours."""

    a = color_a.lstrip("#")
    b = color_b.lstrip("#")
    ra, ga, ba = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
    rb, gb, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    r = int(_lerp(ra, rb, t))
    g = int(_lerp(ga, gb, t))
    b_val = int(_lerp(ba, bb, t))
    return f"#{r:02x}{g:02x}{b_val:02x}"


def _draw_background(canvas: tk.Canvas, width: int, height: int) -> None:
    """Render a vertical gradient with a vignette overlay."""

    steps = max(height // 6, 1)
    for i in range(steps):
        t = i / max(steps - 1, 1)
        color = _lerp_hex(COL_BG_TOP, COL_BG_BOTTOM, t)
        canvas.create_rectangle(
            0,
            i * height / steps,
            width,
            (i + 1) * height / steps,
            outline="",
            fill=color,
            tags=("background",),
        )
    # Vignette overlay
    vignette_radius = max(width, height)
    canvas.create_oval(
        -vignette_radius * 0.25,
        -vignette_radius * 0.25,
        width + vignette_radius * 0.25,
        height + vignette_radius * 0.25,
        fill=COL_BG_VIGNETTE,
        outline="",
        stipple="gray25",
        tags=("background",),
    )


def _trim_to_circle(x1: float, y1: float, x2: float, y2: float, r: float = NODE_R) -> Tuple[float, float, float, float]:
    """Trim a segment so it meets the edge of two circular nodes."""

    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return x1, y1, x2, y2
    trim = min(r / dist, 0.48)
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
    """Return control points for a quadratic bezier with a perpendicular offset."""

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
    color: str = COL_EDGE,
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
    color: str = COL_EDGE,
    width: float = EDGE_WIDTH,
    arrowshape: Tuple[int, int, int] = ARROWSHAPE,
    tags: Tuple[str, ...] = (),
) -> int:
    """Draw a self-loop as a smooth arc with an arrow head."""

    loop_r = r * 1.6
    ctrl = r * 1.2
    points = [
        x,
        y - r,
        x + loop_r,
        y - loop_r - ctrl,
        x,
        y - loop_r * 2,
        x - loop_r,
        y - loop_r - ctrl,
        x,
        y - r,
    ]
    return canvas.create_line(
        *points,
        fill=color,
        width=width,
        smooth=True,
        splinesteps=32,
        arrow=tk.LAST,
        arrowshape=arrowshape,
        capstyle=tk.ROUND,
        tags=("edge",) + tags,
    )


# Layout container ----------------------------------------------------------------
@dataclass
class LayoutState:
    positions: Dict[str, Tuple[float, float]]
    velocities: Dict[str, Tuple[float, float]]


class GraphCanvas(tk.Canvas):
    """Interactive canvas supporting zoom, pan, overlays, and hint chips."""

    def __init__(self, master: tk.Widget, **kwargs: object) -> None:
        super().__init__(master, background=COL_BG_BOTTOM, highlightthickness=0, **kwargs)
        self.master = master
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
        self.node_colors: Dict[int, str] = {}
        self.edge_colors: Dict[int, str] = {}
        self._halo_items: Dict[int, Tuple[str, str]] = {}
        self._pv_items: List[int] = []
        self.on_node_click: Optional[Callable[[str, str], None]] = None
        self._pan_start: Optional[Tuple[float, float]] = None
        self._pulse_phase = 0.0
        self._pv_phase = 0.0
        self._animation_job: Optional[str] = None
        self._chip_frame: Optional[ttk.Frame] = None
        self._chip_buttons: Dict[str, ttk.Button] = {}

        self.bind("<Configure>", self._on_configure)
        self.bind("<ButtonPress-2>", self._on_pan_start)
        self.bind("<B2-Motion>", self._on_pan_drag)
        self.bind("<ButtonRelease-2>", self._on_pan_end)
        self.bind("<Control-MouseWheel>", self._on_zoom)
        self.bind("<MouseWheel>", self._on_zoom)
        self.bind("<Button-4>", self._on_zoom)
        self.bind("<Button-5>", self._on_zoom)
        self.bind("<Button-1>", self._on_click)
        self.tag_bind("edge", "<Enter>", self._on_edge_enter)
        self.tag_bind("edge", "<Leave>", self._on_edge_leave)
        self.tag_bind("node", "<Enter>", self._on_node_enter)
        self.tag_bind("node", "<Leave>", self._on_node_leave)

        self._start_animation()

    # Public API -----------------------------------------------------------------
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
        self.hints_a = [str(h) for h in hints_a]
        self.hints_b = [str(h) for h in hints_b]
        self.pv = list(pv)
        self.heatmap = heatmap
        self.redraw()

    def set_overlays(self, *, hints: Optional[bool] = None, pv: Optional[bool] = None) -> None:
        if hints is not None:
            self.show_hints = hints
        if pv is not None:
            self.show_pv = pv
        self.redraw()

    def set_click_callback(self, callback: Callable[[str, str], None]) -> None:
        self.on_node_click = callback

    def render_hint_chips(self, options: Dict[str, Iterable[str]]) -> None:
        """Render a horizontal bar of hint chips beneath the canvas."""

        if self._chip_frame is None:
            self._chip_frame = ttk.Frame(self.master)
            self._chip_frame.pack(after=self, fill="x", padx=8, pady=(4, 0))
        for child in self._chip_frame.winfo_children():
            child.destroy()
        self._chip_buttons.clear()
        if not self.show_hints:
            return
        for side in ("A", "B"):
            nodes = [str(n) for n in options.get(side, [])]
            if not nodes:
                continue
            heading = ttk.Label(self._chip_frame, text=f"{side} replies:")
            heading.pack(side="left", padx=(0, 6))
            for node in nodes:
                key = f"{side}:{node}"
                btn = ttk.Button(
                    self._chip_frame,
                    text=node,
                    command=lambda s=side, n=node: self._handle_chip_click(s, n),
                    style="Accent.TButton",
                )
                btn.pack(side="left", padx=2, pady=2)
                self._chip_buttons[key] = btn

    # Interaction -----------------------------------------------------------------
    def _on_configure(self, _event: tk.Event) -> None:
        self.redraw()

    def _on_pan_start(self, event: tk.Event) -> None:
        self._pan_start = (event.x, event.y)

    def _on_pan_drag(self, event: tk.Event) -> None:
        if self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self.offset = (self.offset[0] + dx, self.offset[1] + dy)
        self._pan_start = (event.x, event.y)
        self.redraw()

    def _on_pan_end(self, _event: tk.Event) -> None:
        self._pan_start = None

    def _on_zoom(self, event: tk.Event) -> None:
        ctrl_down = getattr(event, "state", 0) & 0x0004
        if not ctrl_down and getattr(event, "delta", 0) and event.widget == self:
            # Only zoom on Ctrl+wheel for standard mouse wheel
            return
        if getattr(event, "delta", 0):
            direction = 1 if event.delta > 0 else -1
        elif getattr(event, "num", None) in (4, 5):
            direction = 1 if event.num == 4 else -1
        else:
            return
        factor = 1.1 if direction > 0 else 0.9
        self.scale_factor = max(0.4, min(2.5, self.scale_factor * factor))
        self.redraw()

    def _on_click(self, event: tk.Event) -> None:
        item = self.find_withtag("current")
        if not item:
            return
        node = self.node_items.get(item[0])
        if node and self.on_node_click:
            self.on_node_click(*node)

    def _handle_chip_click(self, side: str, node: str) -> None:
        if self.on_node_click:
            self.on_node_click(side, node)

    # Layout & drawing ------------------------------------------------------------
    def _compute_layout(self, graph: DiGraph) -> LayoutState:
        positions: Dict[str, Tuple[float, float]] = {}
        velocities: Dict[str, Tuple[float, float]] = {}
        nodes = sorted(graph.succ.keys())
        count = max(len(nodes), 1)
        radius = 160
        for index, node in enumerate(nodes):
            angle = 2 * math.pi * index / count
            positions[node] = (math.cos(angle) * radius, math.sin(angle) * radius)
            velocities[node] = (0.0, 0.0)
        # Simple force-directed relaxation
        for _ in range(20):
            forces = {v: [0.0, 0.0] for v in positions}
            for u in positions:
                for v in positions:
                    if u == v:
                        continue
                    dx = positions[u][0] - positions[v][0]
                    dy = positions[u][1] - positions[v][1]
                    dist_sq = dx * dx + dy * dy + 0.01
                    rep = 16000 / dist_sq
                    forces[u][0] += dx * rep
                    forces[u][1] += dy * rep
            for u, vs in graph.succ.items():
                for v in vs:
                    if v not in positions:
                        continue
                    dx = positions[v][0] - positions[u][0]
                    dy = positions[v][1] - positions[u][1]
                    attr = 0.02
                    forces[u][0] += dx * attr
                    forces[u][1] += dy * attr
                    forces[v][0] -= dx * attr
                    forces[v][1] -= dy * attr
            for node in positions:
                vx, vy = velocities[node]
                vx = (vx + forces[node][0]) * 0.82
                vy = (vy + forces[node][1]) * 0.82
                x, y = positions[node]
                positions[node] = (x + vx * 0.01, y + vy * 0.01)
                velocities[node] = (vx, vy)
        return LayoutState(positions, velocities)

    def redraw(self) -> None:
        self.delete("all")
        self.node_items.clear()
        self.node_colors.clear()
        self.edge_colors.clear()
        self._halo_items.clear()
        self._pv_items.clear()

        if not self.graph_a or not self.graph_b:
            return

        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        _draw_background(self, width, height)
        # Ensure the gradient background stays behind subsequent drawings.
        self.tag_lower("background")

        mid_x = width / 2
        mid_y = height / 2
        offset_x, offset_y = self.offset
        scale = self.scale_factor
        node_radius = NODE_R * scale
        arrowshape = tuple(max(4, int(s * scale)) for s in ARROWSHAPE)
        edge_width = max(1.2, EDGE_WIDTH * scale)

        palettes = {"A": COL_NODE_A, "B": COL_NODE_B}
        current_nodes = {"A": self.position.A_curr, "B": self.position.B_curr}
        hints_map = {
            "A": set(self.hints_a if self.show_hints else []),
            "B": set(self.hints_b if self.show_hints else []),
        }

        def project(px: float, py: float, *, side: str) -> Tuple[float, float]:
            cx = mid_x * 0.5 if side == "A" else mid_x * 1.5
            return (
                cx + (px + offset_x) * scale,
                mid_y + (py + offset_y) * scale,
            )

        # Draw edges for both graphs
        for side, graph in (("A", self.graph_a), ("B", self.graph_b)):
            layout = self.layout.get(side)
            if layout is None:
                continue
            current = current_nodes.get(side)
            forward_targets = set(graph.succ.get(current, set())) if current else set()
            backward_sources = set(graph.pred.get(current, set())) if current else set()
            hints = hints_map[side]
            jump_targets = {h for h in hints if h not in forward_targets and h not in backward_sources}
            for u, vs in graph.succ.items():
                if u not in layout.positions:
                    continue
                for v in vs:
                    if v not in layout.positions:
                        continue
                    x1_raw, y1_raw = layout.positions[u]
                    x2_raw, y2_raw = layout.positions[v]
                    x1, y1 = project(x1_raw, y1_raw, side=side)
                    x2, y2 = project(x2_raw, y2_raw, side=side)
                    tags = (f"edge:{side}:{u}->{v}",)
                    color = EDGE_COLOR or COL_EDGE
                    if current:
                        if u == current and v in forward_targets:
                            color = EDGE_FORWARD
                        elif v == current and u in backward_sources:
                            color = EDGE_BACKWARD
                    if u == current and v in jump_targets:
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
                        offset = _curve_offset(u, v, mag=18.0) * scale
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

        # Draw PV overlay after base edges
        if self.show_pv and self.pv:
            pv_positions = {"A": self.position.A_curr, "B": self.position.B_curr}
            for move in self.pv:
                source = pv_positions.get(move.side)
                if not source:
                    continue
                graph = self.graph_a if move.side == "A" else self.graph_b
                layout = self.layout.get(move.side)
                if layout is None:
                    continue
                if source not in layout.positions or move.dest not in layout.positions:
                    pv_positions[move.side] = move.dest
                    continue
                x1_raw, y1_raw = layout.positions[source]
                x2_raw, y2_raw = layout.positions[move.dest]
                x1, y1 = project(x1_raw, y1_raw, side=move.side)
                x2, y2 = project(x2_raw, y2_raw, side=move.side)
                reverse = source in graph.pred.get(move.dest, set()) and source != move.dest
                offset = _curve_offset(source, move.dest, mag=22.0) * scale if reverse else 0.0
                item = _draw_directed_edge(
                    self,
                    x1,
                    y1,
                    x2,
                    y2,
                    color=COL_PV_EDGE,
                    width=edge_width * 2.0,
                    curved=reverse,
                    offset=offset,
                    node_radius=node_radius,
                    arrowshape=arrowshape,
                    tags=("pv",),
                )
                self._pv_items.append(item)
                pv_positions[move.side] = move.dest

        # Draw nodes
        for side, graph in (("A", self.graph_a), ("B", self.graph_b)):
            layout = self.layout.get(side)
            if layout is None:
                continue
            current = current_nodes.get(side)
            hints = hints_map[side]
            base_fill = palettes[side]
            for node, (x_raw, y_raw) in layout.positions.items():
                px, py = project(x_raw, y_raw, side=side)
                heat = self._heat_intensity(side, node)
                fill = _lerp_hex(base_fill, COL_HEAT_HIGH, heat) if heat > 0 else base_fill
                shadow = self.create_oval(
                    px - node_radius + 3,
                    py - node_radius + 3,
                    px + node_radius + 3,
                    py + node_radius + 3,
                    fill="#000000",
                    outline="",
                    stipple="gray50",
                    tags=("shadow",),
                )
                self.tag_lower(shadow)
                if node == current:
                    halo = self.create_oval(
                        px - node_radius - 8,
                        py - node_radius - 8,
                        px + node_radius + 8,
                        py + node_radius + 8,
                        outline=COL_NODE_CURR,
                        width=4,
                        tags=("current_glow",),
                    )
                    self._halo_items[halo] = (side, node)
                if node in hints:
                    halo = self.create_oval(
                        px - node_radius - 12,
                        py - node_radius - 12,
                        px + node_radius + 12,
                        py + node_radius + 12,
                        outline=COL_HINT_HALO,
                        width=3,
                        dash=(6, 4),
                        tags=("halo", f"halo:{side}:{node}"),
                    )
                    self._halo_items[halo] = (side, node)
                node_item = self.create_oval(
                    px - node_radius,
                    py - node_radius,
                    px + node_radius,
                    py + node_radius,
                    fill=fill,
                    outline="#111827",
                    width=2,
                    tags=("node", f"node:{side}:{node}"),
                )
                self.node_items[node_item] = (side, node)
                self.node_colors[node_item] = fill
                self.tag_raise(node_item)
                # Label with shadow
                font_size = int(10 * max(0.6, scale))
                self.create_text(
                    px + 1,
                    py + 1,
                    text=str(node),
                    fill=COL_LABEL_SHADOW,
                    font=("Helvetica", font_size, "bold"),
                    tags=("label",),
                )
                self.create_text(
                    px,
                    py,
                    text=str(node),
                    fill=COL_LABEL,
                    font=("Helvetica", font_size, "bold"),
                    tags=("label",),
                )

        self.render_hint_chips({"A": self.hints_a, "B": self.hints_b})

    # Animation -------------------------------------------------------------------
    def _start_animation(self) -> None:
        if self._animation_job is None:
            self._animation_job = self.after(PULSE_INTERVAL_MS, self._tick)

    def _tick(self) -> None:
        self._animation_job = None
        self._pulse_phase = (self._pulse_phase + PULSE_SPEED) % (2 * math.pi)
        self._pv_phase = (self._pv_phase + PV_SPEED) % 12.0
        self._animate_halos()
        self._animate_pv()
        self._start_animation()

    def _animate_halos(self) -> None:
        if not self._halo_items:
            return
        pulse = (math.sin(self._pulse_phase) + 1) / 2
        color = _lerp_hex(COL_HINT_HALO, "#ffffff", pulse * 0.35)
        for halo_id in list(self._halo_items):
            if self.type(halo_id):
                self.itemconfigure(halo_id, outline=color)

    def _animate_pv(self) -> None:
        if not self._pv_items:
            return
        dash_offset = self._pv_phase
        for item in self._pv_items:
            if self.type(item):
                self.itemconfigure(item, dash=(10, 6), dashoffset=dash_offset)

    # Hover effects ---------------------------------------------------------------
    def _on_edge_enter(self, event: tk.Event) -> None:
        iid = event.widget.find_withtag("current")
        if not iid:
            return
        item_id = iid[0]
        base = self.edge_colors.get(item_id, COL_EDGE)
        highlight = _lerp_hex(base, COL_EDGE_HOVER, 0.5)
        event.widget.itemconfigure(item_id, fill=highlight)

    def _on_edge_leave(self, event: tk.Event) -> None:
        iid = event.widget.find_withtag("current")
        if not iid:
            return
        item_id = iid[0]
        base = self.edge_colors.get(item_id, COL_EDGE)
        event.widget.itemconfigure(item_id, fill=base)

    def _on_node_enter(self, event: tk.Event) -> None:
        iid = event.widget.find_withtag("current")
        if not iid:
            return
        item_id = iid[0]
        base = self.node_colors.get(item_id)
        if base:
            highlight = _lerp_hex(base, "#ffffff", 0.35)
            event.widget.itemconfigure(item_id, fill=highlight)

    def _on_node_leave(self, event: tk.Event) -> None:
        iid = event.widget.find_withtag("current")
        if not iid:
            return
        item_id = iid[0]
        base = self.node_colors.get(item_id)
        if base:
            event.widget.itemconfigure(item_id, fill=base)

    # Heat helpers ----------------------------------------------------------------
    def _heat_intensity(self, side: str, node: str) -> float:
        if not self.heatmap:
            return 0.0
        total = max(self.heatmap.values())
        if total <= 0:
            return 0.0
        return self.heatmap.get((side, node), 0) / total

    # Cleanup ---------------------------------------------------------------------
    def destroy(self) -> None:  # pragma: no cover - Tk teardown
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)
            self._animation_job = None
        super().destroy()
