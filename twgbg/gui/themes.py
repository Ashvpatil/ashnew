"""Custom ttk themes and palette utilities."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict


THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "background": "#0b1020",
        "surface": "#111827",
        "foreground": "#e5e7eb",
        "accent": "#22c55e",
        "accent_hover": "#34d399",
        "button_fg": "#051019",
        "border": "#1f2937",
    },
    "high_contrast": {
        "background": "#050505",
        "surface": "#111111",
        "foreground": "#f5f5f5",
        "accent": "#facc15",
        "accent_hover": "#fde047",
        "button_fg": "#000000",
        "border": "#27272a",
    },
    "colorblind": {
        "background": "#0a1120",
        "surface": "#131b2c",
        "foreground": "#f4f4f5",
        "accent": "#38bdf8",
        "accent_hover": "#60a5fa",
        "button_fg": "#07121d",
        "border": "#1f2937",
    },
}


def _apply_palette(style: ttk.Style, palette: Dict[str, str], root: tk.Misc) -> None:
    """Apply palette colours to ttk style widgets."""

    bg = palette["background"]
    fg = palette["foreground"]
    accent = palette["accent"]
    accent_hover = palette["accent_hover"]
    surface = palette["surface"]
    button_fg = palette["button_fg"]
    border = palette["border"]

    root.configure(bg=bg)
    style.configure("TFrame", background=bg)
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=surface, foreground=fg, padding=(12, 6))
    style.map(
        "TNotebook.Tab",
        background=[("selected", accent)],
        foreground=[("selected", button_fg)],
    )
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure(
        "TButton",
        background=surface,
        foreground=fg,
        borderwidth=0,
        padding=(10, 6),
        focuscolor=bg,
    )
    style.map(
        "TButton",
        background=[("active", accent_hover)],
        foreground=[("active", button_fg)],
    )
    style.configure(
        "Accent.TButton",
        background=accent,
        foreground=button_fg,
        borderwidth=0,
        padding=(12, 6),
        focuscolor=accent,
    )
    style.map(
        "Accent.TButton",
        background=[("active", accent_hover)],
        foreground=[("active", button_fg)],
    )
    style.configure(
        "Hint.TButton",
        background=surface,
        foreground=fg,
        borderwidth=0,
        padding=(6, 4),
    )
    style.map(
        "Hint.TButton",
        background=[("active", accent_hover)],
        foreground=[("active", button_fg)],
    )
    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.configure("TRadiobutton", background=bg, foreground=fg)
    style.configure("Horizontal.TScale", background=bg)
    style.configure("TSeparator", background=border)


class ThemeManager:
    """Manage ttk palette variations for the application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.current = "dark"
        _apply_palette(self.style, THEMES[self.current], root)

    def apply(self, name: str) -> None:
        palette = THEMES.get(name, THEMES["dark"])
        self.current = name if name in THEMES else "dark"
        _apply_palette(self.style, palette, self.root)

    def palette(self) -> Dict[str, str]:
        return THEMES[self.current].copy()
