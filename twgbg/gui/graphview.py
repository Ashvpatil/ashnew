"""Graph visualisation widgets."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from ..engine.graphs import DiGraph
from ..engine.game import Move
from .themes import DARK_PALETTE


@dataclass
class NodeState:
    pos: QPointF
    item: QGraphicsEllipseItem
    label: QGraphicsSimpleTextItem


class GraphScene(QGraphicsScene):
    def __init__(self, graph: DiGraph, palette=DARK_PALETTE) -> None:
        super().__init__()
        self.graph = graph
        self.palette = palette
        self.node_items: Dict[str, NodeState] = {}
        self.edge_items: Dict[Tuple[str, str], QGraphicsPathItem] = {}
        self.pv_items: List[QGraphicsPathItem] = []
        self.halo_items: Dict[str, QGraphicsEllipseItem] = {}
        self.setBackgroundBrush(QBrush(self.palette.background))
        self.layout_graph()

    def layout_graph(self) -> None:
        n = len(self.graph.vertices())
        radius = 180
        for i, vertex in enumerate(self.graph.vertices()):
            angle = (2 * math.pi * i) / max(1, n)
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            self._create_node(vertex, QPointF(x, y))
        for u, v in self.graph.edges():
            self._create_edge(u, v)

    def _create_node(self, vertex: str, position: QPointF) -> None:
        ellipse = QGraphicsEllipseItem(-20, -20, 40, 40)
        ellipse.setBrush(QBrush(self.palette.surface))
        ellipse.setPen(QPen(self.palette.accent, 2))
        ellipse.setZValue(1)
        meta = self.graph.metadata(vertex)
        tooltip = f"Vertex: {meta.label}\nOut-degree: {len(self.graph.successors(vertex))}\nIn-degree: {len(self.graph.predecessors(vertex))}"
        ellipse.setToolTip(tooltip)
        label = QGraphicsSimpleTextItem(self.graph.metadata(vertex).label, ellipse)
        label.setBrush(QBrush(self.palette.text))
        label.setPos(-label.boundingRect().width() / 2, -label.boundingRect().height() / 2)
        halo = QGraphicsEllipseItem(-28, -28, 56, 56, ellipse)
        halo.setBrush(Qt.NoBrush)
        halo.setPen(QPen(self.palette.accent_alt, 2, Qt.DashLine))
        halo.setOpacity(0.0)
        self.addItem(ellipse)
        ellipse.setPos(position)
        self.node_items[vertex] = NodeState(position, ellipse, label)
        self.halo_items[vertex] = halo

    def _create_edge(self, u: str, v: str) -> None:
        path_item = QGraphicsPathItem()
        path = self._edge_path(self.node_items[u].pos, self.node_items[v].pos)
        path_item.setPath(path)
        path_item.setPen(QPen(self.palette.text_muted, 1.5))
        path_item.setZValue(0)
        self.addItem(path_item)
        self.edge_items[(u, v)] = path_item

    def _edge_path(self, p1: QPointF, p2: QPointF):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath(p1)
        mid = (p1 + p2) / 2
        offset = QPointF(-(p2.y() - p1.y()) * 0.1, (p2.x() - p1.x()) * 0.1)
        path.quadTo(mid + offset, p2)
        return path

    def highlight_nodes(self, vertices: Iterable[str], opacity: float = 1.0) -> None:
        visible = set(vertices)
        for vertex, halo in self.halo_items.items():
            halo.setOpacity(opacity if vertex in visible else 0.0)

    def colour_nodes(self, weights: Dict[str, float]) -> None:
        if not weights:
            return
        max_weight = max(weights.values()) or 1.0
        for vertex, state in self.node_items.items():
            weight = weights.get(vertex, 0.0)
            intensity = min(1.0, weight / max_weight)
            color = QColor(self.palette.accent)
            color.setAlphaF(0.3 + 0.7 * intensity)
            state.item.setBrush(QBrush(color))

    def reset_colours(self) -> None:
        for state in self.node_items.values():
            state.item.setBrush(QBrush(self.palette.surface))

    def show_pv(self, path_vertices: Sequence[str]) -> None:
        for item in self.pv_items:
            self.removeItem(item)
        self.pv_items.clear()
        if len(path_vertices) < 2:
            return
        for a, b in zip(path_vertices, path_vertices[1:]):
            if a not in self.node_items or b not in self.node_items:
                continue
            path_item = QGraphicsPathItem()
            path_item.setPath(self._edge_path(self.node_items[a].pos, self.node_items[b].pos))
            pen = QPen(self.palette.accent_alt, 4)
            pen.setCosmetic(True)
            path_item.setPen(pen)
            path_item.setOpacity(0.6)
            path_item.setZValue(2)
            self.addItem(path_item)
            self.pv_items.append(path_item)


class GraphView(QGraphicsView):
    def __init__(self, graph: DiGraph, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHints(
            self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        self.scene = GraphScene(graph)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.zoom_factor = 1.15

    def wheelEvent(self, event):  # pragma: no cover - GUI interaction
        if event.angleDelta().y() > 0:
            factor = self.zoom_factor
        else:
            factor = 1 / self.zoom_factor
        self.scale(factor, factor)

    def centre_on_vertex(self, vertex: str) -> None:
        if vertex in self.scene.node_items:
            self.centerOn(self.scene.node_items[vertex].item)

    def animate_move(self, move: Move) -> None:
        if move.target not in self.scene.node_items:
            return
        target_item = self.scene.node_items[move.target].item
        anim = QPropertyAnimation(target_item, b"opacity")
        anim.setDuration(400)
        anim.setStartValue(0.3)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def set_heatmap(self, visit_counts: Dict[str, int]) -> None:
        self.scene.reset_colours()
        self.scene.colour_nodes({vertex: float(count) for vertex, count in visit_counts.items()})

    def clear_heatmap(self) -> None:
        self.scene.reset_colours()

    def show_hints(self, vertices: Iterable[str]) -> None:
        self.scene.highlight_nodes(vertices, opacity=1.0)

    def clear_hints(self) -> None:
        self.scene.highlight_nodes([], opacity=0.0)

    def set_pv(self, vertices: Sequence[str]) -> None:
        self.scene.show_pv(vertices)
