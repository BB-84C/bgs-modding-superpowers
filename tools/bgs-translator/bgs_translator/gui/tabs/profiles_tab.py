"""Profiles tab for the Tk control panel.

Lists profiles from ``profiles.toml`` on the left, shows the selected
profile's read-only details on the right, and exposes Add / Delete /
Edit buttons. Edit/Add and key entry are MVP placeholders that point
the user at the .env file as instructed by the spec.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, load_profiles
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.widgets.secret_input import SecretInput

log = logging.getLogger(__name__)


class ProfilesTab(ttk.Frame):
    """Profiles list + read-only detail pane."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(12, 10))
        self._config: ProfilesConfig = ProfilesConfig()
        self._selected_name: str | None = None

        # Header --------------------------------------------------------
        ttk.Label(self, text=_("Profiles"), style="Phosphor.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Left: profile list -------------------------------------------
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self._listbox = tk.Listbox(
            left,
            exportselection=False,
            activestyle="dotbox",
            relief="flat",
            highlightthickness=0,
        )
        self._listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(left, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=list_scroll.set)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        left_actions = ttk.Frame(left, padding=(0, 6))
        left_actions.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Button(
            left_actions,
            text=_("Add new profile"),
            command=self._on_add,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            left_actions,
            text=_("Delete"),
            command=self._on_delete,
        ).pack(side="left")

        # Right: detail pane -------------------------------------------
        right = ttk.Frame(paned, padding=(10, 6))
        paned.add(right, weight=3)
        right.columnconfigure(1, weight=1)

        self._detail_vars: dict[str, tk.StringVar] = {}
        detail_rows = [
            ("Name", "name"),
            ("SDK kind", "sdk_kind"),
            ("Base URL", "base_url"),
            ("Model", "model"),
            ("Concurrency", "max_concurrency"),
            ("Cost cap", "cost_cap_usd"),
            ("API key env", "api_key_env"),
            ("Prompt caching", "prompt_caching"),
            ("JSON mode", "json_mode"),
            ("Notes", "notes"),
        ]
        for index, (caption, key) in enumerate(detail_rows):
            ttk.Label(right, text=f"{caption}:", style="Dim.TLabel").grid(
                row=index, column=0, sticky="nw", padx=(0, 12), pady=2
            )
            var = tk.StringVar(value="-")
            self._detail_vars[key] = var
            ttk.Label(
                right,
                textvariable=var,
                style="TLabel",
                wraplength=420,
                justify="left",
            ).grid(row=index, column=1, sticky="w", pady=2)

        sep = ttk.Separator(right, orient="horizontal")
        sep.grid(row=len(detail_rows), column=0, columnspan=2, sticky="ew", pady=8)

        # API key write-back: TODO. For MVP, surface a disabled SecretInput
        # plus a friendly pointer to the .env file.
        ttk.Label(right, text=_("API key:"), style="Dim.TLabel").grid(
            row=len(detail_rows) + 1, column=0, sticky="w", padx=(0, 12), pady=2
        )
        self._secret = SecretInput(right, placeholder="", width=40)
        self._secret.grid(row=len(detail_rows) + 1, column=1, sticky="ew", pady=2)
        ttk.Label(
            right,
            text=_("Configure API keys via the .env file under profiles/"),
            style="Dim.TLabel",
            wraplength=440,
        ).grid(row=len(detail_rows) + 2, column=0, columnspan=2, sticky="w", pady=(4, 8))

        right_actions = ttk.Frame(right)
        right_actions.grid(row=len(detail_rows) + 3, column=0, columnspan=2, sticky="w")
        ttk.Button(right_actions, text=_("Edit"), command=self._on_edit).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(right_actions, text=_("Save"), style="Accent.TButton",
                   command=self._on_save).pack(side="left")

        self.refresh()

    # Public API -------------------------------------------------------
    def refresh(self) -> None:
        """Reload ``profiles.toml`` and repopulate the listbox."""

        try:
            self._config = load_profiles()
        except Exception as exc:
            log.warning("Could not load profiles: %s", exc)
            self._config = ProfilesConfig()

        self._listbox.delete(0, "end")
        active_name = self._config.active
        for name in sorted(self._config.profiles.keys()):
            marker = " (active)" if name == active_name else ""
            self._listbox.insert("end", f"{name}{marker}")
        if self._selected_name and self._selected_name in self._config.profiles:
            self._show_profile(self._config.profiles[self._selected_name])
        else:
            self._clear_detail()

    # Internals --------------------------------------------------------
    def _on_select(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self._listbox.curselection()  # type: ignore[no-untyped-call]
        if not selection:
            return
        label = self._listbox.get(int(selection[0]))
        name = label.split(" (active)")[0]
        self._selected_name = name
        if name in self._config.profiles:
            self._show_profile(self._config.profiles[name])

    def _show_profile(self, profile: ProviderProfile) -> None:
        self._detail_vars["name"].set(profile.name)
        self._detail_vars["sdk_kind"].set(profile.sdk_kind)
        self._detail_vars["base_url"].set(profile.base_url)
        self._detail_vars["model"].set(profile.model)
        self._detail_vars["max_concurrency"].set(str(profile.max_concurrency))
        cap = profile.cost_cap_usd
        self._detail_vars["cost_cap_usd"].set(f"${cap:.2f}" if cap is not None else "-")
        self._detail_vars["api_key_env"].set(profile.api_key_env)
        self._detail_vars["prompt_caching"].set("yes" if profile.prompt_caching else "no")
        self._detail_vars["json_mode"].set(profile.json_mode or "-")
        self._detail_vars["notes"].set(profile.notes or "-")

    def _clear_detail(self) -> None:
        for var in self._detail_vars.values():
            var.set("-")

    def _on_add(self) -> None:
        # TODO(Chunk-L.2): dialog with full ProviderProfile form.
        messagebox.showinfo(
            title=_("Add new profile"),
            message=_("Coming soon") + " (Chunk L.2)",
            parent=self,
        )

    def _on_delete(self) -> None:
        if self._selected_name is None:
            return
        # TODO(Chunk-L.2): wire to config.profiles.save_profiles after confirm.
        messagebox.showinfo(
            title=_("Delete"),
            message=_("Coming soon") + " (Chunk L.2)",
            parent=self,
        )

    def _on_edit(self) -> None:
        # TODO(Chunk-L.2): flip detail fields to editable Entry widgets.
        messagebox.showinfo(
            title=_("Edit"),
            message=_("Coming soon") + " (Chunk L.2)",
            parent=self,
        )

    def _on_save(self) -> None:
        # TODO(Chunk-L.2): persist edits + key via save_profiles + .env write.
        messagebox.showinfo(
            title=_("Save"),
            message=_("Coming soon") + " (Chunk L.2)",
            parent=self,
        )


__all__ = ["ProfilesTab"]
