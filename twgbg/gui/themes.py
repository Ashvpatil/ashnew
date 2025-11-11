"""Theme definitions for the GUI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Theme:
    name: str
    background: str
    canvas_gradient: str
    foreground: str
    accent: str
    accent_alt: str
    edge: str
    current_glow: str
    legal_glow: str
    heat_low: str
    heat_high: str
    tooltip_fg: str
    tooltip_bg: str
    tooltip_border: str
    font_family: str = "Helvetica"
    font_size: int = 12


LIGHT = Theme(
    name="Light",
    background="#f6f6f8",
    canvas_gradient="#dfe4ea",
    foreground="#202225",
    accent="#2b6cb0",
    accent_alt="#38a169",
    edge="#4a5568",
    current_glow="#cfe4ff",
    legal_glow="#b2f5ea",
    heat_low="#e2e8f0",
    heat_high="#f56565",
    tooltip_fg="#1a202c",
    tooltip_bg="#edf2f7",
    tooltip_border="#cbd5e0",
)

DARK = Theme(
    name="Dark",
    background="#0f172a",
    canvas_gradient="#1a202c",
    foreground="#f8fafc",
    accent="#60a5fa",
    accent_alt="#f59e0b",
    edge="#475569",
    current_glow="#1e293b",
    legal_glow="#0f766e",
    heat_low="#1f2937",
    heat_high="#ef4444",
    tooltip_fg="#f8fafc",
    tooltip_bg="#111827",
    tooltip_border="#334155",
    font_family="Inter",
)

COLORBLIND = Theme(
    name="Colorblind",
    background="#ffffff",
    canvas_gradient="#e8edf2",
    foreground="#000000",
    accent="#0072B2",
    accent_alt="#009E73",
    edge="#444444",
    current_glow="#d0e9ff",
    legal_glow="#c4f1f9",
    heat_low="#bbbbbb",
    heat_high="#D55E00",
    tooltip_fg="#1f2933",
    tooltip_bg="#ffffff",
    tooltip_border="#94a3b8",
)


THEMES: Dict[str, Theme] = {theme.name: theme for theme in [LIGHT, DARK, COLORBLIND]}


__all__ = ["Theme", "THEMES"]
