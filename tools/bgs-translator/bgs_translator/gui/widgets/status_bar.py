"""Top status bar widget for the Tk control panel.

Shows project, profile, cost, language, theme, and a live-pulse cell so
the user can tell at a glance that the GUI's update loop is alive.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Final

_SEP_CHAR: Final[str] = "\u2502"  # '│'
_PULSE_FRAMES: Final[tuple[str, ...]] = (
    "[. .]",
    "[.. ]",
    "[ ..]",
    "[...]",
)


class StatusBar(ttk.Frame):
    """A one-row status bar shown above the nav tree and tabs.

    Cells: project, profile, cost, language picker, theme picker, pulse.
    The language and theme cells are interactive combo boxes; selecting
    a value invokes the corresponding ``on_*_change`` callback if set.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        languages: list[str],
        themes: list[str],
        on_language_change: Callable[[str], None] | None = None,
        on_theme_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, style="Surface.TFrame", padding=(8, 4))
        self._pulse_index = 0
        self._on_language_change = on_language_change
        self._on_theme_change = on_theme_change

        self._project_var = tk.StringVar(value="-")
        self._profile_var = tk.StringVar(value="-")
        self._cost_var = tk.StringVar(value="$0.00")
        self._lang_var = tk.StringVar(value=languages[0] if languages else "en")
        self._theme_var = tk.StringVar(value=themes[0] if themes else "amber")
        self._pulse_var = tk.StringVar(value=_PULSE_FRAMES[0])

        self._build(languages, themes)

    def _build(self, languages: list[str], themes: list[str]) -> None:
        cells: list[tuple[str, tk.Widget]] = []

        cells.append(("project", self._labelled("Project", self._project_var)))
        cells.append(("profile", self._labelled("Profile", self._profile_var)))
        cells.append(("cost", self._labelled("Cost", self._cost_var)))
        cells.append(("language", self._combo("Language", self._lang_var, languages,
                                              self._lang_changed)))
        cells.append(("theme", self._combo("Theme", self._theme_var, themes,
                                           self._theme_changed)))
        cells.append(
            ("pulse", self._labelled("GUI alive", self._pulse_var, style="StatusAccent.TLabel"))
        )

        for index, (_, widget) in enumerate(cells):
            widget.grid(row=0, column=index * 2, padx=(0, 4), sticky="w")
            if index < len(cells) - 1:
                # Status.TLabel matches the surrounding surface so the
                # separator does not paint a darker block under it.
                sep = ttk.Label(self, text=_SEP_CHAR, style="Status.TLabel")
                sep.grid(row=0, column=index * 2 + 1, padx=(0, 4), sticky="w")

        self.columnconfigure(len(cells) * 2 - 1, weight=1)

    def _labelled(
        self,
        caption: str,
        var: tk.StringVar,
        *,
        style: str = "Status.TLabel",
    ) -> tk.Widget:
        from bgs_translator.gui.i18n import gettext as _

        wrap = ttk.Frame(self, style="Surface.TFrame")
        ttk.Label(wrap, text=f"{_(caption)}:", style="StatusDim.TLabel").pack(
            side="left", padx=(0, 4)
        )
        ttk.Label(wrap, textvariable=var, style=style).pack(side="left")
        return wrap

    def _combo(
        self,
        caption: str,
        var: tk.StringVar,
        values: list[str],
        on_change: Callable[[], None],
    ) -> tk.Widget:
        from bgs_translator.gui.i18n import gettext as _

        wrap = ttk.Frame(self, style="Surface.TFrame")
        ttk.Label(wrap, text=f"{_(caption)}:", style="StatusDim.TLabel").pack(
            side="left", padx=(0, 4)
        )
        combo = ttk.Combobox(
            wrap,
            textvariable=var,
            values=values,
            state="readonly",
            width=max(6, max((len(v) for v in values), default=6) + 1),
        )
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _event: on_change())
        return wrap

    def _lang_changed(self) -> None:
        if self._on_language_change is not None:
            self._on_language_change(self._lang_var.get())

    def _theme_changed(self) -> None:
        if self._on_theme_change is not None:
            self._on_theme_change(self._theme_var.get())

    # Public update API ----------------------------------------------------
    def set_project(self, name: str) -> None:
        self._project_var.set(name or "-")

    def set_profile(self, name: str) -> None:
        self._profile_var.set(name or "-")

    def set_cost(self, cost_usd: float) -> None:
        self._cost_var.set(f"${cost_usd:.2f}")

    def set_language(self, language: str) -> None:
        self._lang_var.set(language)

    def set_theme(self, theme: str) -> None:
        self._theme_var.set(theme)

    def pulse(self) -> None:
        """Advance the pulse animation by one frame."""

        self._pulse_index = (self._pulse_index + 1) % len(_PULSE_FRAMES)
        self._pulse_var.set(_PULSE_FRAMES[self._pulse_index])


__all__ = ["StatusBar"]
