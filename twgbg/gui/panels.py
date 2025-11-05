"""Side panels and controls for the application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict

from ..engine.game import RuleConfig


class RulePanel(ttk.Frame):
    def __init__(self, master: tk.Widget, on_update: Callable[[RuleConfig], None]) -> None:
        super().__init__(master)
        self.on_update = on_update
        self.allow_backward = tk.BooleanVar(value=True)
        self.allow_jump = tk.BooleanVar(value=True)
        self.force_same_graph = tk.StringVar(value="None")
        self.round_limit = tk.IntVar(value=0)
        ttk.Label(self, text="Rules").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Checkbutton(self, text="Allow backward", variable=self.allow_backward, command=self._changed).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(self, text="Allow jumps", variable=self.allow_jump, command=self._changed).grid(row=2, column=0, sticky="w")
        ttk.Label(self, text="Force graph").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.OptionMenu(self, self.force_same_graph, "None", "None", "A", "B", command=lambda _: self._changed()).grid(row=4, column=0, sticky="ew")
        ttk.Label(self, text="Round limit (0=∞)").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(self, textvariable=self.round_limit).grid(row=6, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)

    def _changed(self) -> None:
        cfg = RuleConfig(
            allow_backward=self.allow_backward.get(),
            allow_jump=self.allow_jump.get(),
            force_same_graph=None if self.force_same_graph.get() == "None" else self.force_same_graph.get(),
            round_limit=self.round_limit.get() or None,
        )
        self.on_update(cfg)


class AISettings(ttk.Frame):
    def __init__(self, master: tk.Widget, on_engine_change: Callable[[str], None]) -> None:
        super().__init__(master)
        self.engine = tk.StringVar(value="hybrid")
        ttk.Label(self, text="Spoiler AI").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(self, self.engine, "hybrid", "hybrid", "alphabeta", "mcts", command=lambda _: on_engine_change(self.engine.get())).grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)


class HintPanel(ttk.Frame):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.hints_var = tk.StringVar(value="")
        ttk.Label(self, text="Legal replies").pack(anchor="w")
        self.label = ttk.Label(self, textvariable=self.hints_var, wraplength=180)
        self.label.pack(fill="x")

    def update_hints(self, replies: Dict[str, str]) -> None:
        if not replies:
            self.hints_var.set("No legal replies")
        else:
            self.hints_var.set(", ".join(f"{k}: {v}" for k, v in replies.items()))
