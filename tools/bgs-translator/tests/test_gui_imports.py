"""Lightweight import tests for the GUI package.

Importing must NOT spin up a Tk root window — these checks run under
CI as well as locally. Anything Tk-touching lives in
``test_gui_smoke.py`` and is skipped when ``CI=1``.
"""

from __future__ import annotations


def test_gui_package_imports() -> None:
    import bgs_translator.gui.app  # noqa: F401


def test_theme_modules_import() -> None:
    from bgs_translator.gui.themes import amber, green, mono

    assert amber.THEME.name == "amber"
    assert green.THEME.name == "green"
    assert mono.THEME.name == "mono"


def test_theme_registry_round_trip() -> None:
    from bgs_translator.gui.themes import get_theme, list_themes

    names = list_themes()
    assert {"amber", "green", "mono"} <= set(names)
    assert get_theme("amber").name == "amber"
    assert get_theme("does-not-exist").name == "amber"


def test_widget_module_imports() -> None:
    from bgs_translator.gui.widgets import (  # noqa: F401
        ProgressCell,
        ScrollableFrame,
        SecretInput,
        StatusBar,
        render_progress_bar,
    )


def test_progress_bar_shapes() -> None:
    from bgs_translator.gui.widgets import render_progress_bar

    assert render_progress_bar(0, 10, width=4) == "\u2591" * 4
    assert render_progress_bar(10, 10, width=4) == "\u2593" * 4
    mid = render_progress_bar(5, 10, width=4)
    assert len(mid) == 4
    assert "\u2593" in mid or "\u2592" in mid


def test_i18n_translator_returns_msgid_on_miss() -> None:
    from bgs_translator.gui.i18n import Translator

    en = Translator("en")
    assert en.gettext("Project") == "Project"

    zh = Translator("zh-cn")
    # The catalog should have non-empty Chinese for at least one msgid.
    assert zh.gettext("Project") != ""

    miss = Translator("xx")
    assert miss.gettext("not-a-real-string") == "not-a-real-string"


def test_cli_gui_command_registered() -> None:
    from bgs_translator.cli.app import app

    commands = {cmd.name for cmd in app.registered_commands}
    assert "gui" in commands
