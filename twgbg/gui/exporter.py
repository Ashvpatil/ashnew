"""Export utilities for saving boards and sessions."""
from __future__ import annotations

import json
from tkinter import filedialog
from typing import Dict, Any

from ..engine.notation import serialize


def export_session(history, path: str) -> None:
    with open(path, "w", encoding="utf8") as fh:
        json.dump({"history": serialize(history)}, fh, indent=2)


def save_canvas_png(canvas, path: str) -> None:
    canvas.postscript(file=path + ".ps", colormode="color")


def ask_export_file(defaultextension: str, filetypes):
    return filedialog.asksaveasfilename(defaultextension=defaultextension, filetypes=filetypes)


__all__ = ["export_session", "save_canvas_png", "ask_export_file"]
