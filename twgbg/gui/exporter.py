"""Utilities for exporting scenes and artefacts from the GUI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QGraphicsScene


def export_scene_png(scene: QGraphicsScene, path: str) -> None:
    from PySide6.QtGui import QPixmap

    bounds: QRectF = scene.itemsBoundingRect().adjusted(-16, -16, 16, 16)
    pixmap = QPixmap(int(bounds.width()), int(bounds.height()))
    pixmap.fill(Qt.transparent)  # type: ignore[name-defined]
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    scene.render(painter, target=QRectF(pixmap.rect()), source=bounds)
    painter.end()
    pixmap.save(path, "PNG")


def export_scene_svg(scene: QGraphicsScene, path: str) -> None:
    generator = QSvgGenerator()
    generator.setFileName(str(Path(path)))
    bounds: QRectF = scene.itemsBoundingRect().adjusted(-16, -16, 16, 16)
    generator.setSize(bounds.size().toSize())
    generator.setViewBox(bounds)
    painter = QPainter(generator)
    painter.setRenderHint(QPainter.Antialiasing)
    scene.render(painter)
    painter.end()
