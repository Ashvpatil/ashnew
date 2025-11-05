"""Interactive onboarding tutorial."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Tutorial(ttk.Frame):
    stages = [
        "Stage 1: Welcome to the two-way bisimulation game. Spoiler tries to break symmetry!",
        "Stage 2: Moves come in three flavours: forward, backward and jump. Spoiler picks, Duplicator mirrors.",
        "Stage 3: Try selecting the highlighted reply to learn the mirroring rule.",
        "Stage 4: Spoiler hunts for traps. Watch how the principal variation highlights the plan.",
        "Stage 5: Ready for puzzles? Load presets from the main tab and apply what you learned!",
    ]

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.stage_var = tk.IntVar(value=0)
        self.text_var = tk.StringVar(value=self.stages[0])
        ttk.Label(self, text="Tutorial", font=("Helvetica", 16, "bold")).pack(anchor="w", pady=(0, 8))
        self.text = ttk.Label(self, textvariable=self.text_var, wraplength=500, justify="left")
        self.text.pack(fill="x", pady=6)
        controls = ttk.Frame(self)
        controls.pack(anchor="w", pady=10)
        ttk.Button(controls, text="Previous", command=self.prev_stage).grid(row=0, column=0, padx=4)
        ttk.Button(controls, text="Next", command=self.next_stage).grid(row=0, column=1, padx=4)
        self.progress = ttk.Progressbar(self, maximum=len(self.stages) - 1, variable=self.stage_var)
        self.progress.pack(fill="x", pady=4)

    def prev_stage(self) -> None:
        value = max(0, self.stage_var.get() - 1)
        self.stage_var.set(value)
        self.text_var.set(self.stages[value])

    def next_stage(self) -> None:
        value = min(len(self.stages) - 1, self.stage_var.get() + 1)
        self.stage_var.set(value)
        self.text_var.set(self.stages[value])
