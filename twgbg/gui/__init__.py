"""Qt GUI package for the bisimulation game."""

from __future__ import annotations

from typing import Any

__all__ = ["main"]


def main(*args: Any, **kwargs: Any) -> None:
    """Launch the desktop application lazily.

    Importing :mod:`twgbg.gui` should not immediately load the substantial Qt
    widgets defined in :mod:`twgbg.gui.app`.  Doing so triggered a ``runpy``
    warning on some Python interpreters when the application was started via
    ``python -m`` because the module was imported twice.  Deferring the import
    keeps package initialisation lightweight and avoids that warning while still
    exposing a convenient :func:`main` helper.
    """

    from .app import main as _main

    _main(*args, **kwargs)
