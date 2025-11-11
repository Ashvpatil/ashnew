"""Reusable control panels for the GUI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..engine.game import RuleConfig
from .themes import THEMES


class RulePanel(ttk.LabelFrame):
    def __init__(self, master: tk.Widget, config: RuleConfig, on_change: Callable[[RuleConfig], None]) -> None:
        super().__init__(master, text="Rule configuration")
        self.config_ref = config
        self.on_change = on_change
        self.var_backward = tk.BooleanVar(value=config.allow_backward)
        self.var_jump = tk.BooleanVar(value=config.allow_jump)
        self.var_mirror = tk.BooleanVar(value=config.mirror_mode)
        self.var_force = tk.StringVar(value=config.force_same_graph or "auto")
        self.var_round_limit = tk.IntVar(value=config.round_limit or 0)
        self.var_jump_j = tk.IntVar(value=config.jump_cooldown[0])
        self.var_jump_k = tk.IntVar(value=config.jump_cooldown[1])

        ttk.Checkbutton(self, text="Allow backward edges", variable=self.var_backward, command=self._update).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(self, text="Allow jump moves", variable=self.var_jump, command=self._update).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(self, text="Mirror mode", variable=self.var_mirror, command=self._update).grid(row=2, column=0, sticky="w")

        ttk.Label(self, text="Force Spoiler side").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Radiobutton(self, text="Automatic", value="auto", variable=self.var_force, command=self._update).grid(row=4, column=0, sticky="w")
        ttk.Radiobutton(self, text="Graph A", value="A", variable=self.var_force, command=self._update).grid(row=5, column=0, sticky="w")
        ttk.Radiobutton(self, text="Graph B", value="B", variable=self.var_force, command=self._update).grid(row=6, column=0, sticky="w")

        jump_frame = ttk.Frame(self)
        jump_frame.grid(row=7, column=0, sticky="w", pady=(6, 0))
        ttk.Label(jump_frame, text="Jump window (J/K)").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(jump_frame, from_=0, to=5, width=3, textvariable=self.var_jump_j, command=self._update).grid(row=0, column=1, padx=2)
        ttk.Spinbox(jump_frame, from_=1, to=10, width=3, textvariable=self.var_jump_k, command=self._update).grid(row=0, column=2, padx=2)

        ttk.Label(self, text="Round limit (0=∞)").grid(row=8, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(self, from_=0, to=200, width=5, textvariable=self.var_round_limit, command=self._update).grid(row=9, column=0, sticky="w")

    def _update(self) -> None:
        self.config_ref.allow_backward = self.var_backward.get()
        self.config_ref.allow_jump = self.var_jump.get()
        self.config_ref.mirror_mode = self.var_mirror.get()
        force = self.var_force.get()
        self.config_ref.force_same_graph = None if force == "auto" else force
        self.config_ref.jump_cooldown = (self.var_jump_j.get(), max(self.var_jump_k.get(), 1))
        round_limit = self.var_round_limit.get()
        self.config_ref.round_limit = round_limit if round_limit > 0 else None
        self.on_change(self.config_ref)


class ThemePanel(ttk.LabelFrame):
    def __init__(self, master: tk.Widget, on_theme: Callable[[str], None]) -> None:
        super().__init__(master, text="Theme")
        ttk.Label(self, text="Palette").pack(anchor="w")
        combo = ttk.Combobox(self, values=list(THEMES.keys()), state="readonly")
        combo.current(1)
        combo.pack(fill="x", pady=4)
        combo.bind("<<ComboboxSelected>>", lambda *_: on_theme(combo.get()))


__all__ = ["RulePanel", "ThemePanel"]
