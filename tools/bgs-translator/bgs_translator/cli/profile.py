"""Provider profile CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, NoReturn

import typer

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.config.profiles import ProviderProfile, load_profiles, save_profiles

profile_app = typer.Typer(no_args_is_help=True)


@profile_app.command("add", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def add_profile(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    sdk_kind: Literal["openai", "anthropic", "gemini", "openai-compat"] | None = typer.Option(None, "--sdk-kind"),
    base_url: str | None = typer.Option(None, "--base-url"),
    model: str | None = typer.Option(None, "--model"),
    api_key_env: str | None = typer.Option(None, "--api-key-env"),
    api_key: str | None = typer.Option(None, "--api-key", hidden=True),
    max_concurrency: int = typer.Option(4, "--max-concurrency"),
    rate_limit_rpm: int | None = typer.Option(None, "--rate-limit-rpm"),
    rate_limit_tpm: int | None = typer.Option(None, "--rate-limit-tpm"),
    cost_cap_usd: float | None = typer.Option(None, "--cost-cap-usd"),
    json_mode: Literal["json_object", "json_schema"] | None = typer.Option(None, "--json-mode"),
    require_parameters: bool = typer.Option(False, "--require-parameters"),
    prompt_caching: bool = typer.Option(False, "--prompt-caching"),
    notes: str = typer.Option("", "--notes"),
) -> None:
    """Add or replace a provider profile. API key values are rejected."""

    if api_key is not None or "--api-key" in ctx.args:
        _emit_failure(
            "invalid_argument",
            "API key values are not accepted via CLI. Reference an env var name via --api-key-env.",
            {},
        )
    if sdk_kind is None or base_url is None or model is None or api_key_env is None:
        _emit_failure(
            "invalid_argument",
            "--sdk-kind, --base-url, --model, and --api-key-env are required.",
            {},
        )
    assert sdk_kind is not None
    assert base_url is not None
    assert model is not None
    assert api_key_env is not None
    cfg = load_profiles()
    cfg.profiles[name] = ProviderProfile(
        name=name,
        sdk_kind=sdk_kind,
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        max_concurrency=max_concurrency,
        rate_limit_rpm=rate_limit_rpm,
        rate_limit_tpm=rate_limit_tpm,
        cost_cap_usd=cost_cap_usd,
        notes=notes,
        created_at=datetime.now(UTC),
        prompt_caching=prompt_caching,
        json_mode=json_mode,
        require_parameters=require_parameters,
    )
    save_profiles(cfg)
    _emit_success({"profile": name, "path": str(paths.profiles_toml_path())})


@profile_app.command("list")
def list_profiles() -> None:
    """Show configured provider profiles and the active profile."""

    cfg = load_profiles()
    _emit_success(
        {
            "active": cfg.active,
            "profiles": [
                {
                    "name": profile.name,
                    "sdk_kind": profile.sdk_kind,
                    "model": profile.model,
                    "base_url": profile.base_url,
                    "api_key_env": profile.api_key_env,
                    "active": name == cfg.active,
                }
                for name, profile in sorted(cfg.profiles.items())
            ],
        }
    )


@profile_app.command("show")
def show_profile(name: str) -> None:
    """Show one provider profile."""

    cfg = load_profiles()
    profile = cfg.profiles.get(name)
    if profile is None:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    assert profile is not None
    _emit_success({"profile": profile.model_dump(mode="json")})


@profile_app.command("activate")
def activate_profile(name: str) -> None:
    """Set the active provider profile."""

    cfg = load_profiles()
    if name not in cfg.profiles:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    cfg.active = name
    save_profiles(cfg)
    _emit_success({"active": name})


@profile_app.command("remove")
def remove_profile(name: str, yes: bool = typer.Option(False, "--yes")) -> None:
    """Remove a provider profile."""

    if not yes:
        _emit_failure("confirmation_required", "Pass --yes to remove a profile.", {})
    cfg = load_profiles()
    if name not in cfg.profiles:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    del cfg.profiles[name]
    if cfg.active == name:
        cfg.active = None
    save_profiles(cfg)
    _emit_success({"removed": name})


@profile_app.command("edit")
def edit_profile(
    name: str,
    model: str | None = typer.Option(None, "--model"),
    cost_cap_usd: float | None = typer.Option(None, "--cost-cap-usd"),
) -> None:
    """Edit profile fields via flags, or open profiles.toml in $EDITOR."""

    cfg = load_profiles()
    profile = cfg.profiles.get(name)
    if profile is None:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    assert profile is not None
    changed = False
    if model is not None:
        profile.model = model
        changed = True
    if cost_cap_usd is not None:
        profile.cost_cap_usd = cost_cap_usd
        changed = True
    if changed:
        save_profiles(cfg)
        _emit_success({"profile": name, "edited": True})
        return
    editor = os.environ.get("EDITOR")
    if not editor:
        _emit_failure("editor_not_configured", "$EDITOR is not set; use edit flags instead.", {})
    assert editor is not None
    subprocess.run([editor, str(paths.profiles_toml_path())], check=False)
    _emit_success({"profile": name, "editor": editor})


@profile_app.command("probe")
def probe_profile(name: str) -> None:
    """Write a lightweight probe-cache entry without making real API calls."""

    cfg = load_profiles()
    profile = cfg.profiles.get(name)
    if profile is None:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    assert profile is not None
    cache_path = paths.profiles_root() / ".probe-cache.json"
    payload = {
        "probe_id": f"probe_{uuid.uuid4().hex}",
        "profile": name,
        "sdk_kind": profile.sdk_kind,
        "model": profile.model,
        "rate_limit_headers_observed": False,
        "probed_at": datetime.now(UTC).isoformat(),
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _emit_success(payload | {"cache_path": str(cache_path)})


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> NoReturn:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["profile_app"]
