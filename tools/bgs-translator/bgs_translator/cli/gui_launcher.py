"""CLI launcher for the translator control panel.

``xtl gui`` runs the browser control panel in the foreground. Theme and
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
    backend: Annotated[
        str,
        typer.Option("--backend", help="GUI backend: tk or web"),
    ] = "web",
    port: Annotated[
        int | None,
        typer.Option("--port", help="Web GUI localhost port"),
    ] = None,
    no_open: Annotated[
        bool,
        typer.Option("--no-open", help="Do not open a browser tab for the web backend"),
    ] = False,
    native: Annotated[
        bool,
        typer.Option("--native", help="Use NiceGUI native wrapper for the web backend"),
    ] = False,
) -> None:
    """Launch the control panel."""

    if backend == "web":
        from bgs_translator.web.app import launch_web

        launch_web(theme=theme, language=language, port=port, no_open=no_open, native=native)
        return
    if backend != "tk":
        raise typer.BadParameter("backend must be 'tk' or 'web'")

    # Import inside the function so ``--help`` does not pull in Tk/NiceGUI.
    from bgs_translator.gui.app import launch

    launch(theme=theme, language=language)


__all__ = ["launch_gui"]
