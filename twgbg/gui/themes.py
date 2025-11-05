"""Custom ttk themes for the application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


THEMES = {
    "dark": {
        "background": "#1e1e2e",
        "foreground": "#f8f8f2",
        "accent": "#82aaff",
        "node": "#4f8cc9",
    },
    "high_contrast": {
        "background": "#000000",
        "foreground": "#ffffff",
        "accent": "#ffcc00",
        "node": "#ff8800",
    },
    "colorblind": {
        "background": "#2d2a32",
        "foreground": "#f5f5f5",
        "accent": "#6bd0ff",
        "node": "#f08ca0",
    },
}


class ThemeManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.style = ttk.Style(root)
        self.current = "dark"
        self.apply("dark")

    def apply(self, name: str) -> None:
        theme = THEMES.get(name, THEMES["dark"])
        self.current = name
        bg = theme["background"]
        fg = theme["foreground"]
        accent = theme["accent"]
        self.root.configure(bg=bg)
        style = self.style
        style.theme_use("clam")
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=accent, foreground=bg, padding=6)
        style.configure("Accent.TButton", background=accent, foreground=bg, padding=8)
        style.map("TButton", background=[("active", accent)])

    def palette(self) -> dict[str, str]:
        return THEMES[self.current]
