"""Colour palettes and typography helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from PySide6.QtGui import QColor, QFont


@dataclass
class Palette:
    background: QColor
    surface: QColor
    surface_alt: QColor
    accent: QColor
    accent_alt: QColor
    text: QColor
    text_muted: QColor
    success: QColor
    warning: QColor
    danger: QColor


DARK_PALETTE = Palette(
    background=QColor("#141821"),
    surface=QColor("#1E2433"),
    surface_alt=QColor("#262C3E"),
    accent=QColor("#7C4DFF"),
    accent_alt=QColor("#00E5FF"),
    text=QColor("#F5F7FA"),
    text_muted=QColor("#AAB2C8"),
    success=QColor("#4CAF50"),
    warning=QColor("#FFC107"),
    danger=QColor("#EF5350"),
)

HIGH_CONTRAST_PALETTE = Palette(
    background=QColor("#000000"),
    surface=QColor("#111111"),
    surface_alt=QColor("#1C1C1C"),
    accent=QColor("#FF4081"),
    accent_alt=QColor("#64FFDA"),
    text=QColor("#FFFFFF"),
    text_muted=QColor("#E0E0E0"),
    success=QColor("#76FF03"),
    warning=QColor("#FFEA00"),
    danger=QColor("#FF3D00"),
)


FONTS: Dict[str, QFont] = {
    "title": QFont("Fira Sans", 22, QFont.Bold),
    "subtitle": QFont("Fira Sans", 16),
    "body": QFont("Inter", 12),
    "mono": QFont("JetBrains Mono", 11),
}
