"""Interactive graph canvas with force-directed layout and overlays."""
from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from ..engine.graphs import DiGraph
from .themes import Theme


@dataclass
class NodeVisual:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    item: Optional[int] = None
    halo_item: Optional[int] = None
    label_item: Optional[int] = None


class GraphView(tk.Canvas):
    def __init__(self, master: tk.Widget, theme: Theme, *, width: int = 520, height: int = 520) -> None:
        super().__init__(master, width=width, height=height, highlightthickness=0)
        self.theme = theme
        self.graph: Optional[DiGraph] = None
        self.nodes: Dict[str, NodeVisual] = {}
        self.current_node: Optional[str] = None
        self.legal_nodes: List[str] = []
        self.pv_nodes: List[str] = []
        self.heatmap: Dict[str, float] = {}
        self.signature_map: Dict[str, str] = {}
        self._click_callback: Optional[Callable[[str], None]] = None
        self._hover_label: Optional[int] = None
        self._pan_origin: Optional[Tuple[int, int]] = None
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._scale = 1.0
        self._pulse_phase = 0.0
        self._animation_running = False
        self.configure(background=self.theme.background)
        self.bind("<Button-1>", self._handle_click)
        self.bind("<Motion>", self._handle_motion)
        self.bind("<Leave>", lambda _: self._clear_hover())
        self.bind("<MouseWheel>", self._handle_zoom)
        self.bind("<ButtonPress-2>", self._start_pan)
        self.bind("<B2-Motion>", self._do_pan)
        self.bind("<ButtonRelease-2>", lambda _: self._end_pan())

    # ------------------------------------------------------------------
    def set_on_click(self, callback: Callable[[str], None]) -> None:
        self._click_callback = callback

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.background)
        self.redraw()

    def set_graph(self, graph: DiGraph) -> None:
        self.graph = graph
        self._initialise_layout()
        if not self._animation_running:
            self._animation_running = True
            self.after(30, self._animate)
        self.redraw()

    def set_current(self, node: Optional[str]) -> None:
        self.current_node = node
        self.redraw()

    def set_legal(self, nodes: Iterable[str]) -> None:
        self.legal_nodes = list(nodes)
        self.redraw()

    def set_pv(self, nodes: Iterable[str]) -> None:
        self.pv_nodes = list(nodes)
        self.redraw()

    def set_heatmap(self, heat: Dict[str, float]) -> None:
        self.heatmap = heat
        self.redraw()

    def set_signature_map(self, mapping: Dict[str, str]) -> None:
        self.signature_map = mapping
        self.redraw()

    # ------------------------------------------------------------------
    def redraw(self) -> None:
        self.delete("all")
        self._draw_background()
        if not self.graph:
            return
        for u in self.graph.vertices():
            for v in self.graph.successors(u):
                self._draw_edge(u, v)
        if self.pv_nodes:
            self._draw_pv()
        for node, visual in self.nodes.items():
            self._draw_node(node, visual)

    # ------------------------------------------------------------------
    def _initialise_layout(self) -> None:
        if not self.graph:
            return
        w = int(self["width"])
        h = int(self["height"])
        vertices = self.graph.vertices()
        if not vertices:
            return
        self.nodes.clear()
        for idx, vertex in enumerate(vertices):
            angle = 2 * math.pi * idx / len(vertices)
            x = w / 2 + math.cos(angle) * (min(w, h) * 0.35)
            y = h / 2 + math.sin(angle) * (min(w, h) * 0.35)
            self.nodes[vertex] = NodeVisual(x=x, y=y)

    def _animate(self) -> None:
        if not self.graph:
            self._animation_running = False
            return
        self._layout_step()
        self._pulse_phase = (self._pulse_phase + 0.08) % (2 * math.pi)
        self.redraw()
        self.after(60, self._animate)

    def _layout_step(self) -> None:
        if not self.graph:
            return
        width = int(self["width"])
        height = int(self["height"])
        area = width * height
        k = math.sqrt(area / max(1, len(self.nodes)))
        disp: Dict[str, List[float]] = {node: [0.0, 0.0] for node in self.nodes}
        # Repulsive forces
        for v in self.nodes:
            for u in self.nodes:
                if u == v:
                    continue
                dx = self.nodes[v].x - self.nodes[u].x
                dy = self.nodes[v].y - self.nodes[u].y
                dist_sq = dx * dx + dy * dy + 0.01
                force = k * k / dist_sq
                disp[v][0] += (dx / math.sqrt(dist_sq)) * force
                disp[v][1] += (dy / math.sqrt(dist_sq)) * force
        # Attractive forces
        for u in self.graph.vertices():
            for v in self.graph.successors(u):
                if u not in self.nodes or v not in self.nodes:
                    continue
                dx = self.nodes[u].x - self.nodes[v].x
                dy = self.nodes[u].y - self.nodes[v].y
                dist = math.sqrt(dx * dx + dy * dy) + 0.01
                force = (dist * dist) / k
                disp[u][0] -= (dx / dist) * force
                disp[u][1] -= (dy / dist) * force
                disp[v][0] += (dx / dist) * force
                disp[v][1] += (dy / dist) * force
        # Update positions
        for node, (dx, dy) in disp.items():
            visual = self.nodes[node]
            visual.vx = (visual.vx + dx) * 0.5
            visual.vy = (visual.vy + dy) * 0.5
            visual.x = min(width - 40, max(40, visual.x + visual.vx))
            visual.y = min(height - 40, max(40, visual.y + visual.vy))

    def _draw_background(self) -> None:
        w = int(self["width"])
        h = int(self["height"])
        gradient_steps = 6
        for i in range(gradient_steps):
            ratio = i / gradient_steps
            color = self._blend(self.theme.background, self.theme.canvas_gradient, ratio)
            self.create_rectangle(0, h * ratio, w, h * (ratio + 1 / gradient_steps), outline="", fill=color)
        self.create_oval(-w * 0.1, -h * 0.1, w * 1.1, h * 1.1, outline="", fill="", width=4)

    def _draw_edge(self, u: str, v: str) -> None:
        if u not in self.nodes or v not in self.nodes:
            return
        src = self.nodes[u]
        dst = self.nodes[v]
        angle = math.atan2(dst.y - src.y, dst.x - src.x)
        curvature = 18 if v in self.graph.successors(u) and u in self.graph.successors(v) else 0
        offset = 24
        start = (src.x + math.cos(angle) * offset, src.y + math.sin(angle) * offset)
        end = (dst.x - math.cos(angle) * offset, dst.y - math.sin(angle) * offset)
        mid = (
            (start[0] + end[0]) / 2 + math.sin(angle) * curvature,
            (start[1] + end[1]) / 2 - math.cos(angle) * curvature,
        )
        line = self.create_line(
            start[0],
            start[1],
            mid[0],
            mid[1],
            end[0],
            end[1],
            smooth=True,
            width=2,
            arrow=tk.LAST,
            arrowshape=(12, 14, 6),
            fill=self.theme.edge,
            tags=("edge", f"edge:{u}->{v}"),
        )
        self.tag_bind(line, "<Enter>", lambda _e, u=u, v=v: self._highlight_edge(u, v, True))
        self.tag_bind(line, "<Leave>", lambda _e, u=u, v=v: self._highlight_edge(u, v, False))

    def _draw_node(self, node: str, visual: NodeVisual) -> None:
        theme = self.theme
        radius = 18
        weight = self.heatmap.get(node, 0.0)
        fill = self._heat_color(weight)
        outline = theme.edge
        if node == self.current_node:
            self.create_oval(
                visual.x - radius - 8,
                visual.y - radius - 8,
                visual.x + radius + 8,
                visual.y + radius + 8,
                outline="",
                fill=theme.current_glow,
            )
            outline = theme.accent
        if node in self.legal_nodes:
            pulse = (math.sin(self._pulse_phase) + 1) * 0.5
            size = radius + 6 + pulse * 6
            self.create_oval(
                visual.x - size,
                visual.y - size,
                visual.x + size,
                visual.y + size,
                outline="",
                fill=theme.legal_glow,
                stipple="gray25",
            )
        item = self.create_oval(
            visual.x - radius,
            visual.y - radius,
            visual.x + radius,
            visual.y + radius,
            fill=fill,
            outline=outline,
            width=2,
            tags=("node", node),
        )
        label = self.create_text(
            visual.x,
            visual.y,
            text=node,
            fill=theme.foreground,
            font=(theme.font_family, theme.font_size, "bold"),
        )
        self.tag_bind(item, "<Enter>", lambda _e, node=node: self._show_hover(node))
        self.tag_bind(item, "<Leave>", lambda _e: self._clear_hover())
        self.tag_bind(item, "<Button-1>", lambda _e, node=node: self._emit_click(node))
        visual.item = item
        visual.label_item = label

    def _draw_pv(self) -> None:
        for idx in range(len(self.pv_nodes) - 1):
            u = self.pv_nodes[idx]
            v = self.pv_nodes[idx + 1]
            if u not in self.nodes or v not in self.nodes:
                continue
            src = self.nodes[u]
            dst = self.nodes[v]
            self.create_line(
                src.x,
                src.y,
                dst.x,
                dst.y,
                fill=self.theme.accent,
                width=4,
                arrow=tk.LAST,
                arrowshape=(16, 18, 8),
            )

    # ------------------------------------------------------------------
    def _show_hover(self, node: str) -> None:
        if self._hover_label:
            self.delete(self._hover_label)
        info = node
        if self.graph:
            succ = len(self.graph.successors(node))
            pred = len(self.graph.predecessors(node))
            sig = self.signature_map.get(node, "")
            if sig:
                info += f"\nσ={sig}"
            info += f"\nout:{succ} in:{pred}"
        self._hover_label = self.create_text(
            self.nodes[node].x + 30,
            self.nodes[node].y - 30,
            text=info,
            fill=self.theme.tooltip_fg,
            font=(self.theme.font_family, self.theme.font_size - 1),
            anchor="w",
            tags="tooltip",
        )
        bbox = self.bbox(self._hover_label)
        if bbox:
            rect = self.create_rectangle(
                bbox[0] - 6,
                bbox[1] - 4,
                bbox[2] + 6,
                bbox[3] + 4,
                fill=self.theme.tooltip_bg,
                outline=self.theme.tooltip_border,
            )
            self.tag_lower(rect, self._hover_label)

    def _clear_hover(self) -> None:
        if self._hover_label:
            self.delete(self._hover_label)
            self._hover_label = None
        self.delete("tooltip")

    def _highlight_edge(self, u: str, v: str, active: bool) -> None:
        color = self.theme.accent if active else self.theme.edge
        self.itemconfig(f"edge:{u}->{v}", fill=color)

    def _emit_click(self, node: str) -> None:
        if self._click_callback:
            self._click_callback(node)

    def _handle_click(self, event: tk.Event) -> None:
        closest = None
        best_dist = float("inf")
        for node, visual in self.nodes.items():
            dx = event.x - visual.x
            dy = event.y - visual.y
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                closest = node
        if closest and self._click_callback:
            self._click_callback(closest)

    def _handle_motion(self, event: tk.Event) -> None:
        if not self.nodes:
            return
        closest = None
        best_dist = 9000
        for node, visual in self.nodes.items():
            dx = event.x - visual.x
            dy = event.y - visual.y
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                closest = node
        if closest:
            self._show_hover(closest)

    def _handle_zoom(self, event: tk.Event) -> None:
        factor = 1.1 if event.delta > 0 else 0.9
        self._scale *= factor
        self.scale("all", event.x, event.y, factor, factor)

    def _start_pan(self, event: tk.Event) -> None:
        self._pan_origin = (event.x, event.y)

    def _do_pan(self, event: tk.Event) -> None:
        if not self._pan_origin:
            return
        dx = event.x - self._pan_origin[0]
        dy = event.y - self._pan_origin[1]
        self._offset_x += dx
        self._offset_y += dy
        self.move("all", dx, dy)
        self._pan_origin = (event.x, event.y)

    def _end_pan(self) -> None:
        self._pan_origin = None

    # ------------------------------------------------------------------
    def _heat_color(self, weight: float) -> str:
        weight = min(max(weight, 0.0), 1.0)
        return self._blend(self.theme.heat_low, self.theme.heat_high, weight)

    def _blend(self, start: str, end: str, ratio: float) -> str:
        ratio = min(max(ratio, 0.0), 1.0)
        sr, sg, sb = tuple(int(start[i : i + 2], 16) for i in (1, 3, 5))
        er, eg, eb = tuple(int(end[i : i + 2], 16) for i in (1, 3, 5))
        r = int(sr + (er - sr) * ratio)
        g = int(sg + (eg - sg) * ratio)
        b = int(sb + (eb - sb) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"


__all__ = ["GraphView"]
