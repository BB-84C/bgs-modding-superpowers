"""Profiles tab for provider configuration and API-key write path."""

from __future__ import annotations

import logging
import subprocess
import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Literal

from pydantic import ValidationError

from bgs_translator.config import paths
from bgs_translator.config.profiles import (
    ProfilesConfig,
    ProviderProfile,
    load_profiles,
    save_profiles,
    write_env_var,
)
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.secret_input import SecretInput

log = logging.getLogger(__name__)

SdkKind = Literal["openai", "anthropic", "gemini", "openai-compat"]


class ProfileDialog(tk.Toplevel):
    """Modal add/edit dialog backed by ``ProviderProfile`` validation."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        title: str,
        config: ProfilesConfig,
        profile: ProviderProfile | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.resizable(False, False)
        self._config = config
        self._profile = profile
        self._on_saved = on_saved
        self.values: dict[str, tk.StringVar] = {
            "name": tk.StringVar(value=profile.name if profile else ""),
            "sdk_kind": tk.StringVar(value=profile.sdk_kind if profile else "openai"),
            "base_url": tk.StringVar(value=profile.base_url if profile else "https://api.openai.com/v1"),
            "model": tk.StringVar(value=profile.model if profile else ""),
            "api_key_env": tk.StringVar(value=profile.api_key_env if profile else "BGS_TRANSLATOR_KEY_"),
            "max_concurrency": tk.StringVar(value=str(profile.max_concurrency) if profile else "4"),
            "rate_limit_rpm": tk.StringVar(value=str(profile.rate_limit_rpm or "") if profile else ""),
            "cost_cap_usd": tk.StringVar(value=str(profile.cost_cap_usd if profile and profile.cost_cap_usd is not None else "10.00")),
            "json_mode": tk.StringVar(value=profile.json_mode or "json_schema" if profile else "json_schema"),
            "notes": tk.StringVar(value=profile.notes if profile else ""),
        }
        self.prompt_caching_var = tk.BooleanVar(value=bool(profile.prompt_caching) if profile else False)
        self.error_var = tk.StringVar(value="")

        body = ttk.Frame(self, padding=(14, 12))
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)

        rows: list[tuple[str, str, str]] = [
            (_("Name"), "name", "entry"),
            (_("SDK kind"), "sdk_kind", "combo"),
            (_("Base URL"), "base_url", "entry"),
            (_("Model"), "model", "entry"),
            (_("API key env"), "api_key_env", "entry"),
            (_("Max concurrency"), "max_concurrency", "entry"),
            (_("Rate limit RPM"), "rate_limit_rpm", "entry"),
            (_("Cost cap USD"), "cost_cap_usd", "entry"),
            (_("JSON mode"), "json_mode", "json_combo"),
            (_("Notes"), "notes", "entry"),
        ]
        for row, (caption, key, kind) in enumerate(rows):
            ttk.Label(body, text=f"{caption}:", style="Dim.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            if kind == "combo":
                ttk.Combobox(
                    body,
                    textvariable=self.values[key],
                    values=("openai", "anthropic", "gemini", "openai-compat"),
                    state="readonly",
                    width=26,
                ).grid(row=row, column=1, sticky="ew", pady=3)
            elif kind == "json_combo":
                ttk.Combobox(
                    body,
                    textvariable=self.values[key],
                    values=("json_object", "json_schema"),
                    state="readonly",
                    width=26,
                ).grid(row=row, column=1, sticky="ew", pady=3)
            else:
                ttk.Entry(body, textvariable=self.values[key], width=34).grid(row=row, column=1, sticky="ew", pady=3)

        prompt_row = len(rows)
        ttk.Label(body, text=f"{_('Prompt caching')}:", style="Dim.TLabel").grid(row=prompt_row, column=0, sticky="w", padx=(0, 10), pady=3)
        ttk.Checkbutton(body, variable=self.prompt_caching_var).grid(row=prompt_row, column=1, sticky="w", pady=3)
        ttk.Label(
            body,
            text=_("API key value goes in profiles/.env separately. Use the [Set key] button on the profile detail pane."),
            style="Dim.TLabel",
            wraplength=420,
        ).grid(row=prompt_row + 1, column=0, columnspan=2, sticky="w", pady=(8, 4))
        ttk.Label(body, textvariable=self.error_var, style="Dim.TLabel", wraplength=420).grid(
            row=prompt_row + 2, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        buttons = ttk.Frame(body)
        buttons.grid(row=prompt_row + 3, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text=_("Save"), style="Accent.TButton", command=self.save).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text=_("Cancel"), command=self.destroy).pack(side="left")

    def save(self) -> bool:
        """Validate and persist the profile. Returns True on success."""

        name = self.values["name"].get().strip()
        sdk_kind = self.values["sdk_kind"].get().strip()
        json_mode = self.values["json_mode"].get().strip() if sdk_kind == "openai-compat" else ""
        try:
            profile = ProviderProfile(
                name=name,
                sdk_kind=sdk_kind,  # type: ignore[arg-type]
                base_url=self.values["base_url"].get().strip(),
                model=self.values["model"].get().strip(),
                api_key_env=self.values["api_key_env"].get().strip(),
                max_concurrency=int(self.values["max_concurrency"].get().strip() or "4"),
                rate_limit_rpm=_optional_int(self.values["rate_limit_rpm"].get()),
                cost_cap_usd=_optional_float(self.values["cost_cap_usd"].get()),
                prompt_caching=self.prompt_caching_var.get(),
                json_mode=(json_mode or None),  # type: ignore[arg-type]
                notes=self.values["notes"].get().strip(),
                created_at=self._profile.created_at if self._profile else None,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            self.error_var.set(str(exc))
            return False
        if self._profile is not None and self._profile.name != name:
            self._config.profiles.pop(self._profile.name, None)
            if self._config.active == self._profile.name:
                self._config.active = name
        self._config.profiles[name] = profile
        save_profiles(self._config)
        self.event_generate("<<ProfilesChanged>>")
        if self._on_saved is not None:
            self._on_saved()
        self.destroy()
        return True


class SetApiKeyDialog(tk.Toplevel):
    """Modal dialog that writes the selected profile's API key to .env."""

    def __init__(self, master: tk.Misc, *, profile: ProviderProfile, on_saved: Callable[[], None] | None = None) -> None:
        super().__init__(master)
        self.title(_("Set API key for {name}").format(name=profile.name))
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self._profile = profile
        self._on_saved = on_saved
        self.error_var = tk.StringVar(value="")

        body = ttk.Frame(self, padding=(14, 12))
        body.grid(row=0, column=0, sticky="nsew")
        ttk.Label(body, text=f"{_('Env var')}: {profile.api_key_env}", style="Dim.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(body, text=f"{_('Key')}:", style="Dim.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.secret = SecretInput(body, width=42)
        self.secret.grid(row=1, column=1, sticky="ew")
        ttk.Label(body, text=_("will be stored in profiles/.env, 0600"), style="Dim.TLabel").grid(row=2, column=1, sticky="w", pady=(4, 8))
        ttk.Label(body, textvariable=self.error_var, style="Dim.TLabel").grid(row=3, column=0, columnspan=2, sticky="w")
        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text=_("Save"), style="Accent.TButton", command=self.save).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text=_("Cancel"), command=self.destroy).pack(side="left")

    def save(self) -> bool:
        try:
            write_env_var(paths.profiles_env_path(), self._profile.api_key_env, self.secret.get())
        except (OSError, ValueError) as exc:
            self.error_var.set(str(exc))
            return False
        self.secret.set("")
        if self._on_saved is not None:
            self._on_saved()
        self.destroy()
        return True


class ProfilesTab(ttk.Frame):
    """Profiles list + detail pane with profile actions."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(12, 10))
        self._config: ProfilesConfig = ProfilesConfig()
        self._selected_name: str | None = None
        self.probe_result_var = tk.StringVar(value="")

        ttk.Label(self, text=_("Profiles"), style="Phosphor.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self._listbox = tk.Listbox(left, exportselection=False, activestyle="dotbox", relief="flat", highlightthickness=0)
        self._listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll = AmberScrollbar(left, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=list_scroll.set)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self._list_scroll = list_scroll
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        left_actions = ttk.Frame(left, padding=(0, 6))
        left_actions.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Button(left_actions, text=_("Add new profile"), command=self._on_add).pack(side="left", padx=(0, 6))
        ttk.Button(left_actions, text=_("Delete"), command=self._on_delete).pack(side="left")

        right = ttk.Frame(paned, padding=(10, 6))
        paned.add(right, weight=3)
        right.columnconfigure(1, weight=1)
        self._detail_vars: dict[str, tk.StringVar] = {}
        detail_rows = [
            (_("Name"), "name"),
            (_("SDK kind"), "sdk_kind"),
            (_("Base URL"), "base_url"),
            (_("Model"), "model"),
            (_("Concurrency"), "max_concurrency"),
            (_("Cost cap"), "cost_cap_usd"),
            (_("API key env"), "api_key_env"),
            (_("Prompt caching"), "prompt_caching"),
            (_("JSON mode"), "json_mode"),
            (_("Notes"), "notes"),
        ]
        for index, (caption, key) in enumerate(detail_rows):
            ttk.Label(right, text=f"{caption}:", style="Dim.TLabel").grid(row=index, column=0, sticky="nw", padx=(0, 12), pady=2)
            var = tk.StringVar(value="-")
            self._detail_vars[key] = var
            ttk.Label(right, textvariable=var, style="TLabel", wraplength=420, justify="left").grid(row=index, column=1, sticky="w", pady=2)

        row = len(detail_rows)
        ttk.Separator(right, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        self._probe_panel = ttk.Label(right, textvariable=self.probe_result_var, style="Dim.TLabel", wraplength=460, justify="left")
        self._probe_panel.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        right_actions = ttk.Frame(right)
        right_actions.grid(row=row + 2, column=0, columnspan=2, sticky="w")
        ttk.Button(right_actions, text=_("Edit"), command=self._on_edit).pack(side="left", padx=(0, 6))
        ttk.Button(right_actions, text=_("Probe"), command=self._on_probe).pack(side="left", padx=(0, 6))
        ttk.Button(right_actions, text=_("Set active"), command=self._on_set_active).pack(side="left", padx=(0, 6))
        ttk.Button(right_actions, text=_("Set API key"), command=self._on_set_key).pack(side="left", padx=(0, 6))
        ttk.Button(right_actions, text=_("Delete"), command=self._on_delete).pack(side="left")

        self.refresh()

    def refresh(self) -> None:
        try:
            self._config = load_profiles()
        except Exception as exc:
            log.warning("Could not load profiles: %s", exc)
            self._config = ProfilesConfig()

        self._listbox.delete(0, "end")
        active_name = self._config.active
        for name in sorted(self._config.profiles.keys()):
            marker = _(" (active)") if name == active_name else ""
            self._listbox.insert("end", f"{name}{marker}")
        if self._selected_name and self._selected_name in self._config.profiles:
            self._show_profile(self._config.profiles[self._selected_name])
        else:
            self._clear_detail()

    def delete_profile(self, name: str, *, confirm: bool = False) -> bool:
        if name not in self._config.profiles:
            return False
        if not confirm:
            ok = messagebox.askokcancel(
                title=_("Delete profile {name}?").format(name=name),
                message=_("This removes the profile from profiles.toml. The API key value in .env is NOT deleted."),
                parent=self,
            )
            if not ok:
                return False
        self._config.profiles.pop(name, None)
        if self._config.active == name:
            self._config.active = None
        if self._selected_name == name:
            self._selected_name = None
        save_profiles(self._config)
        self.refresh()
        self.event_generate("<<ProfilesChanged>>")
        return True

    def probe_profile(self, name: str) -> None:
        cmd = [sys.executable, "-m", "bgs_translator.cli.app", "profile", "probe", name]
        self.probe_result_var.set(_("Probe result for {name}: running...").format(name=name))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            self.probe_result_var.set(_("Probe result for {name}: failed\n{detail}").format(name=name, detail=exc))
            return
        output = (result.stdout or result.stderr or "").strip()
        status = _("Connection successful") if result.returncode == 0 else _("Connection failed")
        self.probe_result_var.set(f"{_('Probe result for {name}').format(name=name)}\n{status}\n{output}")

    def set_active_profile(self, name: str) -> bool:
        if name not in self._config.profiles:
            return False
        self._config.active = name
        save_profiles(self._config)
        self.refresh()
        self.event_generate("<<ProfilesChanged>>")
        return True

    def _on_select(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self._listbox.curselection()  # type: ignore[no-untyped-call]
        if not selection:
            return
        label = self._listbox.get(int(selection[0]))
        name = label.replace(_(" (active)"), "")
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
        self._detail_vars["prompt_caching"].set(_("yes") if profile.prompt_caching else _("no"))
        self._detail_vars["json_mode"].set(profile.json_mode or "-")
        self._detail_vars["notes"].set(profile.notes or "-")

    def _clear_detail(self) -> None:
        for var in self._detail_vars.values():
            var.set("-")
        self.probe_result_var.set("")

    def _selected_profile(self) -> ProviderProfile | None:
        if self._selected_name is None:
            return None
        return self._config.profiles.get(self._selected_name)

    def _on_add(self) -> None:
        ProfileDialog(self, title=_("Add new provider profile"), config=self._config, on_saved=self.refresh)

    def _on_delete(self) -> None:
        if self._selected_name is not None:
            self.delete_profile(self._selected_name)

    def _on_edit(self) -> None:
        profile = self._selected_profile()
        if profile is not None:
            ProfileDialog(self, title=_("Edit provider profile"), config=self._config, profile=profile, on_saved=self.refresh)

    def _on_probe(self) -> None:
        if self._selected_name is not None:
            self.probe_profile(self._selected_name)

    def _on_set_active(self) -> None:
        if self._selected_name is not None:
            self.set_active_profile(self._selected_name)

    def _on_set_key(self) -> None:
        profile = self._selected_profile()
        if profile is not None:
            SetApiKeyDialog(self, profile=profile)


def _optional_int(value: str) -> int | None:
    stripped = value.strip()
    return int(stripped) if stripped else None


def _optional_float(value: str) -> float | None:
    stripped = value.strip()
    return float(stripped) if stripped else None


__all__ = ["ProfileDialog", "ProfilesTab", "SetApiKeyDialog"]
