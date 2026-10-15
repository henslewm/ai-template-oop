"""The Shell: layout, event binding, state. No business logic lives here."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow

__all__ = ["MainWindow"]


def __getattr__(name: str) -> type[MainWindow]:
    """Keep the window export compatible without requiring Tk for mocks."""
    if name == "MainWindow":
        from src.ui.main_window import MainWindow

        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
