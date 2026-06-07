"""Typer root application and Chunk B version command for bgs-translator."""

# TODO(Chunk-B): Expand CLI registration as later command chunks land.

from __future__ import annotations

import json
import platform
from typing import Annotated, Any

import typer

from bgs_translator import __version__
from bgs_translator.cli.batch import batch_app
from bgs_translator.cli.config import config_app
from bgs_translator.cli.edit import edit_app
from bgs_translator.cli.envelopes import success
from bgs_translator.cli.inspect import inspect_app
from bgs_translator.cli.profile import profile_app
from bgs_translator.cli.project import project_app
from bgs_translator.cli.validate import validate_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(batch_app, name="batch")
app.add_typer(config_app, name="config")
app.add_typer(project_app, name="project")
app.add_typer(inspect_app, name="inspect")
app.add_typer(profile_app, name="profile")
app.add_typer(edit_app, name="edit")
app.add_typer(validate_app, name="validate")


@app.callback()
def _root() -> None:
    """bgs-translator command group."""


def _capabilities() -> dict[str, Any]:
    """Return the v0.1.0-dev skeleton capability matrix."""
    return {
        "parser": {"tes3": False, "tes4_family": False},
        "output": {"sst": False, "eet_xml": False},
        "providers": {
            "openai": False,
            "anthropic": False,
            "gemini": False,
            "openai-compat": False,
        },
        "kb": False,
        "gui": False,
    }


@app.command()
def version(
    json_output: Annotated[
        bool,
        typer.Option("--json/--no-json", help="Emit the standard JSON envelope."),
    ] = True,
) -> None:
    """Print the translator version and skeleton capability matrix."""
    envelope = success(
        {
            "version": __version__,
            "python": platform.python_version(),
            "capabilities": _capabilities(),
        }
    )
    if json_output:
        typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))
        return

    typer.echo(f"bgs-translator {__version__}")


def main() -> None:
    """Run the bgs-translator CLI."""
    app()


__all__ = ["app", "main"]
