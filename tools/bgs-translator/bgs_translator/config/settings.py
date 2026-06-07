"""Global settings model and persistence ownership."""

from __future__ import annotations

import logging
import tomllib
from copy import deepcopy
from typing import Any, Literal

import tomli_w
from pydantic import BaseModel, Field, ValidationError

from bgs_translator.config import paths

log = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 1


class UiSettings(BaseModel):
    """User-interface defaults for CLI/GUI surfaces."""

    language: Literal["en", "zh-cn"] = "en"
    theme: Literal["amber", "green", "mono"] = "amber"
    window_width: int = 1440
    window_height: int = 900
    left_panel_width: int = 240


class BehaviorSettings(BaseModel):
    """Global behavior toggles."""

    default_template: str = "default"
    sst_version: Literal["SSU9", "SSU8", "SSU7", "SSU6", "SSU5", "SSU4", "SSU3", "SSU2"] = "SSU9"
    skip_kb_migration: bool = False
    prompt_preview_required: bool = False


class Settings(BaseModel):
    """Complete settings document."""

    schema_version: int = CURRENT_SCHEMA_VERSION
    ui: UiSettings = Field(default_factory=UiSettings)
    behavior: BehaviorSettings = Field(default_factory=BehaviorSettings)


def _read_settings_dict() -> dict[str, Any]:
    settings_file = paths.settings_path()
    if not settings_file.exists():
        return {}
    with settings_file.open("rb") as handle:
        return tomllib.load(handle)


def load_settings() -> Settings:
    """Load settings from disk, merging missing fields with defaults."""
    raw = _read_settings_dict()
    schema_version = raw.get("schema_version")
    if schema_version is not None and schema_version != CURRENT_SCHEMA_VERSION:
        log.warning(
            "Unsupported settings schema_version %s; loading with v%s defaults",
            schema_version,
            CURRENT_SCHEMA_VERSION,
        )
    return Settings.model_validate(raw)


def save_settings(s: Settings) -> None:
    """Persist settings to TOML."""
    settings_file = paths.settings_path()
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(tomli_w.dumps(s.model_dump(mode="python")), encoding="utf-8")


_KEY_ALIASES = {
    "ui_language": "ui.language",
    "ui_theme": "ui.theme",
    "default_template": "behavior.default_template",
    "sst_version": "behavior.sst_version",
    "skip_kb_migration": "behavior.skip_kb_migration",
    "prompt_preview_required": "behavior.prompt_preview_required",
}


def normalize_setting_key(dotted_key: str) -> str:
    """Normalize legacy flat config keys to dotted settings paths."""
    return _KEY_ALIASES.get(dotted_key, dotted_key)


def _set_nested(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = normalize_setting_key(dotted_key).split(".")
    if len(parts) < 2:
        raise KeyError(f"Invalid settings key '{dotted_key}'. Use a dotted key such as 'ui.theme'.")

    cursor: dict[str, Any] = data
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            raise KeyError(f"Invalid settings key '{dotted_key}': '{part}' is not a settings section.")
        cursor = next_value

    leaf = parts[-1]
    if leaf not in cursor:
        raise KeyError(f"Invalid settings key '{dotted_key}': unknown field '{leaf}'.")
    cursor[leaf] = value


def update_setting(dotted_key: str, value: Any) -> Settings:
    """Update one dotted settings key, save it, and return the new settings."""
    current = load_settings()
    data = deepcopy(current.model_dump(mode="python"))
    _set_nested(data, dotted_key, value)
    try:
        updated = Settings.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid value for setting '{dotted_key}': {exc}") from exc
    save_settings(updated)
    return updated


__all__ = [
    "BehaviorSettings",
    "Settings",
    "UiSettings",
    "load_settings",
    "normalize_setting_key",
    "save_settings",
    "update_setting",
]
