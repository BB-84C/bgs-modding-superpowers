"""Config subcommands for bgs-translator."""

from __future__ import annotations

import json
from typing import Any, NoReturn

import typer

from bgs_translator.cli.envelopes import Envelope, exit_code_for, failure, success
from bgs_translator.config import paths
from bgs_translator.config.migrations import (
    migrate_kb_cache,
    migration_needed,
    prompt_user_for_migration_cli,
)
from bgs_translator.config.settings import Settings, load_settings, save_settings, update_setting

config_app = typer.Typer(no_args_is_help=True)


def _emit(envelope: Envelope) -> NoReturn:
    typer.echo(json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2))
    raise typer.Exit(exit_code_for(envelope))


def _settings_payload(settings: Settings) -> dict[str, Any]:
    return settings.model_dump(mode="json")


def _resolved_paths() -> dict[str, str]:
    return {
        "home": str(paths.home()),
        "kb_root": str(paths.kb_root()),
        "translator_root": str(paths.translator_root()),
        "profiles_root": str(paths.profiles_root()),
        "config_root": str(paths.config_root()),
        "logs_root": str(paths.logs_root()),
    }


def _parse_scalar(value: str) -> bool | int | str:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def _get_setting_value(settings: Settings, key: str) -> Any:
    cursor: Any = settings.model_dump(mode="json")
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(f"Invalid settings key '{key}'.")
        cursor = cursor[part]
    return cursor


@config_app.command("show")
def show() -> None:
    """Show global settings and resolved persistence paths."""
    settings = load_settings()
    _emit(success({"settings": _settings_payload(settings), "paths": _resolved_paths()}))


@config_app.command("set")
def set_value(key: str, value: str) -> None:
    """Set a global setting by dotted key path."""
    try:
        updated = update_setting(key, _parse_scalar(value))
    except KeyError as exc:
        _emit(failure("invalid_key", str(exc)))
    except ValueError as exc:
        _emit(failure("invalid_value", str(exc)))
    else:
        _emit(success({"settings": _settings_payload(updated)}))


@config_app.command("get")
def get_value(key: str) -> None:
    """Get one global setting by dotted key path."""
    try:
        value = _get_setting_value(load_settings(), key)
    except KeyError as exc:
        _emit(failure("invalid_key", str(exc)))
    else:
        _emit(success({"key": key, "value": value}))


@config_app.command("reset")
def reset(yes: bool = typer.Option(False, "--yes", help="Reset without confirmation.")) -> None:
    """Reset global settings to defaults."""
    if not yes and not typer.confirm("Reset bgs-translator settings to defaults?", default=False):
        _emit(failure("cancelled", "Settings reset cancelled."))
    settings = Settings()
    save_settings(settings)
    _emit(success({"settings": _settings_payload(settings)}))


@config_app.command("migrate-kb")
def migrate_kb(yes: bool = typer.Option(False, "--yes", help="Migrate without confirmation.")) -> None:
    """Manually trigger the KB cache migration workflow."""
    needed, legacy, reason = migration_needed()
    target = paths.kb_root()
    if not needed or legacy is None:
        _emit(success({"migrated": False, "reason": reason, "target": str(target)}))

    if not yes and not prompt_user_for_migration_cli(legacy, target):
        _emit(failure("cancelled", "KB cache migration cancelled."))

    try:
        migrate_kb_cache(legacy, target)
    except Exception as exc:
        _emit(failure("migration_failed", str(exc)))
    _emit(success({"migrated": True, "legacy": str(legacy), "target": str(target)}))


__all__ = ["config_app"]
