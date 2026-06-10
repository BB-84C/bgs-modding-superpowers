"""Provider profile CLI commands."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, NoReturn

import typer

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.config.profiles import (
    ProfileMissingKeyError,
    ProviderProfile,
    load_profiles,
    normalize_base_url,
    resolve_api_key,
    save_profiles,
    write_env_var,
)
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.clients.base import build_client_for
from bgs_translator.pipeline.mask import build_masked_unit

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
    base_url, stripped_suffix = _normalize_base_url_for_cli(base_url)
    if stripped_suffix is not None:
        typer.echo(
            f"Warning: stripped endpoint suffix {stripped_suffix!r}; base_url is now {base_url!r}.",
            err=True,
        )
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
    base_url: str | None = typer.Option(None, "--base-url"),
    model: str | None = typer.Option(None, "--model"),
    cost_cap_usd: float | None = typer.Option(None, "--cost-cap-usd"),
    max_concurrency: int | None = typer.Option(None, "--max-concurrency"),
    rate_limit_rpm: int | None = typer.Option(None, "--rate-limit-rpm"),
    rate_limit_tpm: int | None = typer.Option(None, "--rate-limit-tpm"),
    json_mode: Literal["json_object", "json_schema"] | None = typer.Option(None, "--json-mode"),
    require_parameters: bool | None = typer.Option(None, "--require-parameters/--no-require-parameters"),
    prompt_caching: bool | None = typer.Option(None, "--prompt-caching/--no-prompt-caching"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    """Edit profile fields via flags, or open profiles.toml in $EDITOR."""

    cfg = load_profiles()
    profile = cfg.profiles.get(name)
    if profile is None:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    assert profile is not None
    changed = False
    if base_url is not None:
        normalized_base_url, stripped_suffix = _normalize_base_url_for_cli(base_url)
        if stripped_suffix is not None:
            typer.echo(
                "Warning: stripped endpoint suffix "
                f"{stripped_suffix!r}; base_url is now {normalized_base_url!r}.",
                err=True,
            )
        profile.base_url = normalized_base_url
        changed = True
    if model is not None:
        profile.model = model
        changed = True
    if cost_cap_usd is not None:
        profile.cost_cap_usd = cost_cap_usd
        changed = True
    if max_concurrency is not None:
        profile.max_concurrency = max_concurrency
        changed = True
    if rate_limit_rpm is not None:
        profile.rate_limit_rpm = rate_limit_rpm
        changed = True
    if rate_limit_tpm is not None:
        profile.rate_limit_tpm = rate_limit_tpm
        changed = True
    if json_mode is not None:
        profile.json_mode = json_mode
        changed = True
    if require_parameters is not None:
        profile.require_parameters = require_parameters
        changed = True
    if prompt_caching is not None:
        profile.prompt_caching = prompt_caching
        changed = True
    if notes is not None:
        profile.notes = notes
        changed = True
    if changed:
        cfg.profiles[name] = ProviderProfile.model_validate(profile.model_dump(mode="python"))
        save_profiles(cfg)
        _emit_success({"profile": name, "edited": True})
        return
    editor = os.environ.get("EDITOR")
    if not editor:
        _emit_failure("editor_not_configured", "$EDITOR is not set; use edit flags instead.", {})
    assert editor is not None
    subprocess.run([editor, str(paths.profiles_toml_path())], check=False)
    _emit_success({"profile": name, "editor": editor})


@profile_app.command("set-key")
def set_profile_key(name: str) -> None:
    """Store a profile API key in profiles/.env via hidden prompt/stdin."""

    cfg = load_profiles()
    profile = cfg.profiles.get(name)
    if profile is None:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    assert profile is not None
    key = typer.prompt(
        f"API key for {name} ({profile.api_key_env})",
        hide_input=True,
        confirmation_prompt=False,
    )
    if not str(key).strip():
        _emit_failure("invalid_argument", "API key cannot be empty.", {})
    write_env_var(paths.profiles_env_path(), profile.api_key_env, str(key).strip())
    _emit_success({"profile": name, "api_key_env": profile.api_key_env, "path": str(paths.profiles_env_path())})


@profile_app.command("probe")
def probe_profile(name: str) -> None:
    """Probe a provider profile with a real minimal provider call."""

    cfg = load_profiles()
    profile = cfg.profiles.get(name)
    if profile is None:
        _emit_failure("profile_not_found", f"Profile {name!r} does not exist.", {})
    assert profile is not None
    try:
        resolve_api_key(profile)
    except ProfileMissingKeyError:
        _emit_failure(
            "missing_api_key",
            "Profile "
            f"{profile.name} requires env var {profile.api_key_env} in profiles/.env; "
            "set it via `xtl profile set-key` or the GUI.",
            {"profile": profile.name, "api_key_env": profile.api_key_env},
        )
    try:
        asyncio.run(_probe_provider(profile))
    except Exception as exc:
        if _is_auth_error(exc):
            _emit_failure("auth_failed", str(exc), {"profile": profile.name})
        _emit_failure("probe_failed", str(exc), {"profile": profile.name})
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


async def _probe_provider(profile: ProviderProfile) -> None:
    client = build_client_for(profile)
    try:
        unit = TranslationUnit("Probe.esp", 1, 1, "PROBE", "MESG", "FULL", source="ping")
        batch = Batch("probe", [build_masked_unit(unit)], None, [], [])
        await client.translate_batch(
            batch,
            "Return a minimal JSON translation object for this connectivity probe.",
        )
    finally:
        await client.aclose()


def _is_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {401, 403}:
        return True
    message = str(exc).casefold()
    return "401" in message or "403" in message or "auth" in message or "unauthorized" in message


def _normalize_base_url_for_cli(value: str) -> tuple[str, str | None]:
    return normalize_base_url(value)


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> NoReturn:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["profile_app"]
