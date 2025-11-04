"""Interactive graph visualisation used by the GUI."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from ..analysis import signature_partition
from ..engine.graphs import DiGraph
from ..engine.game import Move
from .themes import COLORBLIND_SAFE_PALETTE, DARK_PALETTE, HIGH_CONTRAST_PALETTE, Palette


@dataclass
class NodeState:
    position: QPointF
    item: QGraphicsEllipseItem
    label: QGraphicsSimpleTextItem
    halo: QGraphicsEllipseItem


class GraphScene(QGraphicsScene):
    def __init__(self, graph: DiGraph, palette: Palette = DARK_PALETTE) -> None:
        super().__init__()
        self.graph = graph
        self.palette = palette
        self.node_items: Dict[str, NodeState] = {}
        self.edge_items: Dict[tuple, QGraphicsPathItem] = {}
        self.pv_items: List[QGraphicsPathItem] = []
        self.animations: List[QPropertyAnimation] = []
        self.setBackgroundBrush(QBrush(self.palette.background))
        self._build_scene()

    # ------------------------------------------------------------------
    def _build_scene(self) -> None:
        self.clear()
        self.node_items.clear()
        self.edge_items.clear()
        radius = 220
        vertices = self.graph.vertices()
        for index, vertex in enumerate(vertices):
            angle = (2 * math.pi * index) / max(1, len(vertices))
            pos = QPointF(radius * math.cos(angle), radius * math.sin(angle))
            self._create_node(vertex, pos)
        for u, v in self.graph.edges():
            self._create_edge(u, v)
        self._force_layout()
        self.partition_nodes()

    def _create_node(self, vertex: str, pos: QPointF) -> None:
        ellipse = QGraphicsEllipseItem(-26, -26, 52, 52)
        ellipse.setBrush(QBrush(self.palette.surface))
        ellipse.setPen(QPen(self.palette.accent, 2.5))
        ellipse.setZValue(2)
        shadow = QGraphicsDropShadowEffect()
        shadow.setOffset(0, 0)
        shadow.setBlurRadius(18)
        shadow.setColor(self.palette.accent_alt)
        ellipse.setGraphicsEffect(shadow)

        label = QGraphicsSimpleTextItem(self.graph.metadata(vertex).label, ellipse)
        label.setBrush(QBrush(self.palette.text))
        label_rect = label.boundingRect()
        label.setPos(-label_rect.width() / 2, -label_rect.height() / 2)

        halo = QGraphicsEllipseItem(-36, -36, 72, 72, ellipse)
        halo.setBrush(Qt.NoBrush)
        halo.setPen(QPen(self.palette.accent_alt, 3, Qt.DashLine))
        halo.setOpacity(0.0)
        halo.setZValue(3)

        tooltip = self._tooltip(vertex)
        ellipse.setToolTip(tooltip)
        self.addItem(ellipse)
        ellipse.setPos(pos)
        self.node_items[vertex] = NodeState(pos, ellipse, label, halo)

    def _tooltip(self, vertex: str) -> str:
        meta = self.graph.metadata(vertex)
        indeg, outdeg = self.graph.degree(vertex)
        return (
            f"{meta.label}\n"
            f"in/out degree: {indeg}/{outdeg}\n"
            f"signature: {meta.signature or 'N/A'}\n"
            f"cluster: {meta.cluster if meta.cluster is not None else 'N/A'}"
        )

    def _create_edge(self, u: str, v: str) -> None:
        source = self.node_items[u].position
        target = self.node_items[v].position
        path_item = QGraphicsPathItem()
        path_item.setZValue(1)
        path_item.setPen(QPen(self.palette.text_muted, 1.8))
        path_item.setPath(self._edge_path(source, target))
        self.addItem(path_item)
        self.edge_items[(u, v)] = path_item

    def _update_edge(self, u: str, v: str) -> None:
        if (u, v) not in self.edge_items:
            return
        source = self.node_items[u].position
        target = self.node_items[v].position
        self.edge_items[(u, v)].setPath(self._edge_path(source, target))

    def _edge_path(self, source: QPointF, target: QPointF):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath(source)
        if source == target:
            path.addEllipse(source, 18, 18)
            return path
        mid = (source + target) / 2
        offset = QPointF(-(target.y() - source.y()) * 0.18, (target.x() - source.x()) * 0.18)
        path.quadTo(mid + offset, target)
        return path

    # ------------------------------------------------------------------
    def partition_nodes(self) -> None:
        clusters = signature_partition(self.graph)
        for vertex, cluster_id in clusters.items():
            meta = self.graph.metadata(vertex)
            meta.cluster = cluster_id
            meta.signature = meta.signature or f"C{cluster_id}"
            node = self.node_items[vertex]
            node.item.setToolTip(self._tooltip(vertex))

    def _force_layout(self, iterations: int = 60) -> None:
        if len(self.node_items) <= 2:
            return
        area = 800 * 800
        k = math.sqrt(area / max(1, len(self.node_items)))
        positions = {vertex: state.position for vertex, state in self.node_items.items()}
        for _ in range(iterations):
            disp: Dict[str, QPointF] = {vertex: QPointF(0, 0) for vertex in positions}
            for v in positions:
                for u in positions:
                    if u == v:
                        continue
                    delta = positions[v] - positions[u]
                    distance = max(0.01, math.hypot(delta.x(), delta.y()))
                    force = (k * k) / distance
                    disp[v] += delta / distance * force
            for (v, u) in self.graph.edges():
                delta = positions[v] - positions[u]
                distance = max(0.01, math.hypot(delta.x(), delta.y()))
                force = (distance * distance) / k
                disp[v] -= delta / distance * force
                disp[u] += delta / distance * force
            for vertex in positions:
                displacement = disp[vertex]
                distance = max(0.01, math.hypot(displacement.x(), displacement.y()))
                limited = displacement / distance * min(distance, k)
                positions[vertex] += limited
                positions[vertex].setX(max(-350, min(350, positions[vertex].x())))
                positions[vertex].setY(max(-350, min(350, positions[vertex].y())))
        for vertex, pos in positions.items():
            state = self.node_items[vertex]
            state.position = pos
            state.item.setPos(pos)
        for u, v in self.graph.edges():
            self._update_edge(u, v)

    # ------------------------------------------------------------------
    def highlight_vertices(self, vertices: Iterable[str], pulse: bool = True) -> None:
        target = set(vertices)
        self._clear_animations()
        for vertex, state in self.node_items.items():
            state.halo.setOpacity(1.0 if vertex in target else 0.0)
            if pulse and vertex in target:
                anim = QPropertyAnimation(state.halo, b"opacity")
                anim.setDuration(600)
                anim.setStartValue(0.2)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.InOutQuad)
                anim.setLoopCount(-1)
                anim.start()
                self.animations.append(anim)

    def _clear_animations(self) -> None:
        for anim in self.animations:
            anim.stop()
        self.animations.clear()

    def clear_hints(self) -> None:
        self.highlight_vertices([], pulse=False)

    def show_pv(self, vertices: Sequence[str]) -> None:
        for item in self.pv_items:
            self.removeItem(item)
        self.pv_items.clear()
        if len(vertices) < 2:
            return
        for a, b in zip(vertices, vertices[1:]):
            if a not in self.node_items or b not in self.node_items:
                continue
            path = self._edge_path(self.node_items[a].position, self.node_items[b].position)
            stroke = QGraphicsPathItem(path)
            pen = QPen(self.palette.accent_alt, 4)
            pen.setCosmetic(True)
            stroke.setPen(pen)
            stroke.setOpacity(0.65)
            stroke.setZValue(4)
            self.addItem(stroke)
            self.pv_items.append(stroke)

    def apply_heatmap(self, weights: Dict[str, int]) -> None:
        if not weights:
            return
        maximum = max(weights.values()) or 1
        for vertex, state in self.node_items.items():
            weight = weights.get(vertex, 0)
            color = QColor(self.palette.accent)
            color.setAlphaF(0.35 + 0.65 * (weight / maximum))
            state.item.setBrush(QBrush(color))

    def reset_colours(self) -> None:
        for state in self.node_items.values():
            state.item.setBrush(QBrush(self.palette.surface))

    def set_palette(self, palette: Palette) -> None:
        self.palette = palette
        self.setBackgroundBrush(QBrush(self.palette.background))
        for state in self.node_items.values():
            state.item.setBrush(QBrush(self.palette.surface))
            state.item.setPen(QPen(self.palette.accent, 2.5))
            state.label.setBrush(QBrush(self.palette.text))
            state.halo.setPen(QPen(self.palette.accent_alt, 3, Qt.DashLine))
        for edge in self.edge_items.values():
            edge.setPen(QPen(self.palette.text_muted, 1.8))
        self.show_pv([])

    # ------------------------------------------------------------------
    def export_png(self, path: str) -> None:
        bounds: QRectF = self.itemsBoundingRect()
        pixmap = QPixmap(int(bounds.width()) + 50, int(bounds.height()) + 50)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        self.render(painter, target=QRectF(pixmap.rect()), source=bounds.adjusted(-20, -20, 20, 20))
        painter.end()
        pixmap.save(path, "PNG")


class GraphView(QGraphicsView):
    def __init__(self, graph: DiGraph, parent=None) -> None:
        super().__init__(parent)
        self.graph = graph
        self.scene = GraphScene(graph)
        self.setScene(self.scene)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.zoom_factor = 1.18
        self.current_palette = DARK_PALETTE

    # ------------------------------------------------------------------
    def wheelEvent(self, event):  # pragma: no cover - GUI interaction
        factor = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
        self.scale(factor, factor)

    def centre_on(self, vertex: str) -> None:
        if vertex in self.scene.node_items:
            self.centerOn(self.scene.node_items[vertex].item)

    def animate_move(self, move: Move) -> None:
        if move.target not in self.scene.node_items:
            return
        target_item = self.scene.node_items[move.target].item
        anim = QPropertyAnimation(target_item, b"scale")
        anim.setDuration(420)
        anim.setStartValue(1.0)
        anim.setEndValue(1.12)
        anim.setEasingCurve(QEasingCurve.OutBack)
        anim.setLoopCount(2)
        anim.finished.connect(lambda: target_item.setScale(1.0))
        anim.start()
        self.scene.animations.append(anim)

    def show_hints(self, vertices: Iterable[str]) -> None:
        self.scene.highlight_vertices(vertices)

    def clear_hints(self) -> None:
        self.scene.clear_hints()

    def set_pv(self, vertices: Sequence[str]) -> None:
        self.scene.show_pv(vertices)

    def set_heatmap(self, visits: Dict[str, int]) -> None:
        self.scene.reset_colours()
        self.scene.apply_heatmap(visits)

    def clear_heatmap(self) -> None:
        self.scene.reset_colours()

    def set_palette(self, palette: Palette) -> None:
        self.current_palette = palette
        self.scene.set_palette(palette)

    def set_high_contrast(self, enabled: bool) -> None:
        palette = HIGH_CONTRAST_PALETTE if enabled else DARK_PALETTE
        self.set_palette(palette)

    def set_colorblind_safe(self, enabled: bool) -> None:
        palette = COLORBLIND_SAFE_PALETTE if enabled else self.current_palette
        self.set_palette(palette)

    def export_png(self, path: str) -> None:
        self.scene.export_png(path)
