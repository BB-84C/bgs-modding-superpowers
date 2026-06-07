"""CLI launcher for the Tk control panel.

``xtl gui`` runs the Tk control panel in the foreground. Theme and
language can be overridden from the command line; otherwise they fall
back to ``config/settings.toml``.
"""

from __future__ import annotations

from typing import Annotated

import typer


def launch_gui(
    theme: Annotated[
        str | None,
        typer.Option("--theme", help="Override the GUI theme (amber, green, mono)"),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", help="Override the GUI language (en, zh-cn)"),
    ] = None,
) -> None:
    """Launch the Tk control panel."""

    # Import inside the function so ``--help`` does not pull in Tk.
    from bgs_translator.gui.app import launch

    launch(theme=theme, language=language)


__all__ = ["launch_gui"]
