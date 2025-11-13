"""Interactive graph visualisation used by the GUI."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set

from PyQt5.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt5.QtWidgets import (
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
    current_ring: QGraphicsEllipseItem


class ArrowPathItem(QGraphicsPathItem):
    """Edge with an arrow head rendered at its end."""

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.palette = palette
        self.arrow_head = QPolygonF()
        pen = QPen(self.palette.text_muted, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setZValue(1)
        self._show_arrow = True

    def update_geometry(self, path: QPainterPath, show_arrow: bool = True) -> None:
        self.setPath(path)
        self._show_arrow = show_arrow
        if not show_arrow:
            self.arrow_head = QPolygonF()
            return
        if path.elementCount() < 2:
            self.arrow_head = QPolygonF()
            return
        end_point = path.pointAtPercent(1.0)
        angle = math.radians(-path.angleAtPercent(1.0))
        arrow_size = 12.0
        left = end_point + QPointF(
            math.sin(angle + math.pi / 3) * arrow_size,
            math.cos(angle + math.pi / 3) * arrow_size,
        )
        right = end_point + QPointF(
            math.sin(angle - math.pi / 3) * arrow_size,
            math.cos(angle - math.pi / 3) * arrow_size,
        )
        self.arrow_head = QPolygonF([end_point, left, right])

    def paint(self, painter, option, widget=None):  # pragma: no cover - GUI rendering
        super().paint(painter, option, widget)
        if self.arrow_head.isEmpty() or not self._show_arrow:
            return
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.pen().color())
        painter.drawPolygon(self.arrow_head)


class GraphScene(QGraphicsScene):
    def __init__(self, graph: DiGraph, palette: Palette = DARK_PALETTE) -> None:
        super().__init__()
        self.graph = graph
        self.palette = palette
        self.node_items: Dict[str, NodeState] = {}
        self.edge_items: Dict[tuple, ArrowPathItem] = {}
        self.pv_items: List[QGraphicsPathItem] = []
        self.animations: List[QVariantAnimation] = []
        self.current_vertices: Set[str] = set()
        self.setBackgroundBrush(QBrush(self.palette.background))
        self._build_scene()

    # ------------------------------------------------------------------
    def _build_scene(self) -> None:
        self.clear()
        self.node_items.clear()
        self.edge_items.clear()
        radius = 220
        vertices = [str(v) for v in self.graph.vertices()]
        for index, vertex_id in enumerate(vertices):
            angle = (2 * math.pi * index) / max(1, len(vertices))
            pos = QPointF(radius * math.cos(angle), radius * math.sin(angle))
            self._create_node(vertex_id, pos)
        for raw_u, raw_v in self.graph.edges():
            self._create_edge(str(raw_u), str(raw_v))
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
        halo.setBrush(QBrush(Qt.NoBrush))
        halo.setPen(QPen(self.palette.accent_alt, 3, Qt.DashLine))
        halo.setOpacity(0.0)
        halo.setZValue(3)

        current_ring = QGraphicsEllipseItem(-32, -32, 64, 64, ellipse)
        current_ring.setBrush(QBrush(Qt.NoBrush))
        current_ring.setPen(QPen(self.palette.success, 3))
        current_ring.setOpacity(0.0)
        current_ring.setZValue(2.5)

        tooltip = self._tooltip(vertex)
        ellipse.setToolTip(tooltip)
        self.addItem(ellipse)
        ellipse.setPos(pos)
        self.node_items[vertex] = NodeState(pos, ellipse, label, halo, current_ring)

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
        path_item = ArrowPathItem(self.palette)
        path = self._edge_path(source, target)
        show_arrow = source != target
        path_item.update_geometry(path, show_arrow=show_arrow)
        self.addItem(path_item)
        self.edge_items[(u, v)] = path_item

    def _update_edge(self, u: str, v: str) -> None:
        u = str(u)
        v = str(v)
        if (u, v) not in self.edge_items:
            return
        source = self.node_items[u].position
        target = self.node_items[v].position
        path = self._edge_path(source, target)
        show_arrow = source != target
        self.edge_items[(u, v)].update_geometry(path, show_arrow=show_arrow)

    def _edge_path(self, source: QPointF, target: QPointF):
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
        for cluster_id, vertices in clusters.items():
            for vertex in (str(v) for v in vertices):
                if vertex not in self.node_items:
                    continue
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
            for raw_v, raw_u in self.graph.edges():
                v, u = str(raw_v), str(raw_u)
                if v not in positions or u not in positions:
                    continue
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
        for raw_u, raw_v in self.graph.edges():
            self._update_edge(str(raw_u), str(raw_v))

    # ------------------------------------------------------------------
    def highlight_vertices(self, vertices: Iterable[str], pulse: bool = True) -> None:
        target = {str(v) for v in vertices}
        self._clear_animations()
        for vertex, state in self.node_items.items():
            if vertex in target:
                state.halo.setOpacity(1.0)
            else:
                state.halo.setOpacity(0.0)
            if pulse and vertex in target:
                anim = QVariantAnimation(self)
                anim.setDuration(900)
                anim.setStartValue(0.35)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.InOutQuad)
                anim.setLoopCount(-1)
                anim.valueChanged.connect(
                    lambda value, halo=state.halo: halo.setOpacity(float(value))
                )
                anim.start()
                self.animations.append(anim)

    def set_current_vertices(self, vertices: Iterable[str]) -> None:
        self.current_vertices = {str(v) for v in vertices}
        for vertex, state in self.node_items.items():
            is_current = vertex in self.current_vertices
            state.current_ring.setOpacity(0.85 if is_current else 0.0)
            if is_current:
                state.item.setBrush(QBrush(self.palette.surface_alt))
            elif vertex not in self.current_vertices:
                state.item.setBrush(QBrush(self.palette.surface))

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
        for raw_a, raw_b in zip(vertices, vertices[1:]):
            a, b = str(raw_a), str(raw_b)
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
        normalised = {str(vertex): value for vertex, value in weights.items()}
        maximum = max(normalised.values()) or 1
        for vertex, state in self.node_items.items():
            weight = normalised.get(vertex, 0)
            color = QColor(self.palette.accent)
            color.setAlphaF(0.35 + 0.65 * (weight / maximum))
            state.item.setBrush(QBrush(color))
            if vertex in self.current_vertices:
                state.current_ring.setOpacity(0.9)

    def reset_colours(self) -> None:
        for state in self.node_items.values():
            state.item.setBrush(QBrush(self.palette.surface))
            state.current_ring.setOpacity(0.0)
        self.set_current_vertices(self.current_vertices)

    def set_palette(self, palette: Palette) -> None:
        self.palette = palette
        self.setBackgroundBrush(QBrush(self.palette.background))
        for state in self.node_items.values():
            state.item.setBrush(QBrush(self.palette.surface))
            state.item.setPen(QPen(self.palette.accent, 2.5))
            state.label.setBrush(QBrush(self.palette.text))
            state.halo.setPen(QPen(self.palette.accent_alt, 3, Qt.DashLine))
            state.current_ring.setPen(QPen(self.palette.success, 3))
        for edge in self.edge_items.values():
            edge.setPen(QPen(self.palette.text_muted, 1.8))
        self.show_pv([])
        self.set_current_vertices(self.current_vertices)

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
        self.graph_scene = GraphScene(graph)
        self.setScene(self.graph_scene)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.zoom_factor = 1.18
        self.current_palette = DARK_PALETTE
        self.select_callback: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    def wheelEvent(self, event):  # pragma: no cover - GUI interaction
        factor = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
        self.scale(factor, factor)

    def mousePressEvent(self, event):  # pragma: no cover - GUI interaction
        handled = False
        if event.button() == Qt.LeftButton and self.select_callback:
            item = self.itemAt(event.pos())
            if item is not None:
                target_item = item
                if target_item.parentItem() is not None:
                    target_item = target_item.parentItem()
                for vertex, state in self.graph_scene.node_items.items():
                    if target_item is state.item:
                        self.select_callback(vertex)
                        handled = True
                        break
        if not handled:
            super().mousePressEvent(event)

    def centre_on(self, vertex: str) -> None:
        vertex_id = str(vertex)
        if vertex_id in self.graph_scene.node_items:
            self.centerOn(self.graph_scene.node_items[vertex_id].item)

    def animate_move(self, move: Move) -> None:
        target = str(move.target)
        if target not in self.graph_scene.node_items:
            return
        target_item = self.graph_scene.node_items[target].item
        anim = QVariantAnimation(self)
        anim.setDuration(420)
        anim.setStartValue(1.0)
        anim.setEndValue(1.12)
        anim.setEasingCurve(QEasingCurve.OutBack)
        anim.setLoopCount(2)
        anim.valueChanged.connect(
            lambda value, item=target_item: item.setScale(float(value))
        )
        anim.finished.connect(lambda item=target_item: item.setScale(1.0))
        anim.start()
        self.graph_scene.animations.append(anim)

    def show_hints(self, vertices: Iterable[str]) -> None:
        self.graph_scene.highlight_vertices(vertices)

    def clear_hints(self) -> None:
        self.graph_scene.clear_hints()

    def set_pv(self, vertices: Sequence[str]) -> None:
        self.graph_scene.show_pv(vertices)

    def set_heatmap(self, visits: Dict[str, int]) -> None:
        self.graph_scene.reset_colours()
        self.graph_scene.apply_heatmap(visits)

    def clear_heatmap(self) -> None:
        self.graph_scene.reset_colours()

    def set_current(self, vertices: Iterable[str]) -> None:
        self.graph_scene.set_current_vertices(vertices)

    def set_palette(self, palette: Palette) -> None:
        self.current_palette = palette
        self.graph_scene.set_palette(palette)

    def set_high_contrast(self, enabled: bool) -> None:
        palette = HIGH_CONTRAST_PALETTE if enabled else DARK_PALETTE
        self.set_palette(palette)

    def set_colorblind_safe(self, enabled: bool) -> None:
        palette = COLORBLIND_SAFE_PALETTE if enabled else self.current_palette
        self.set_palette(palette)

    def export_png(self, path: str) -> None:
        self.graph_scene.export_png(path)

    def set_select_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self.select_callback = callback
