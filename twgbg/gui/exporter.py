"""Export utilities for the Tkinter canvas and data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

from ..engine.notation import serialize
from ..engine.utils import json_dump


def export_canvas(canvas, path: str) -> str:
    postscript_path = Path(path).with_suffix(".ps")
    canvas.postscript(file=postscript_path)
    if Image is not None:
        img = Image.open(postscript_path)
        png_path = Path(path).with_suffix(".png")
        img.save(png_path)
        return str(png_path)
    return str(postscript_path)


def export_history(history, path: str) -> None:
    json_dump({"notation": serialize(history)}, path)
