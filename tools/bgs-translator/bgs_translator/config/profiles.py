"""Provider profile load, validation, persistence, and key resolution."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import tomli_w
from dotenv import dotenv_values
from pydantic import BaseModel, Field, field_validator, model_validator

from bgs_translator.config import paths

log = logging.getLogger(__name__)

_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
_LITERAL_SECRET_FIELDS = {"api_key", "apikey", "key", "secret", "token"}


class ProfileValidationError(ValueError):
    """Raised when profiles.toml violates translator safety rules."""


class ProfileMissingKeyError(RuntimeError):
    """Raised when the referenced API key cannot be loaded safely."""

    def __init__(self, profile_name: str, api_key_env: str, message: str | None = None) -> None:
        detail = message or f"API key env var {api_key_env!r} is missing for profile {profile_name!r}."
        super().__init__(detail)
        self.profile_name = profile_name
        self.api_key_env = api_key_env


class ProviderProfile(BaseModel):
    """Agent-readable provider profile. API key values are stored separately."""

    name: str
    sdk_kind: Literal["openai", "anthropic", "gemini", "openai-compat"]
    base_url: str
    model: str
    api_key_env: str
    max_concurrency: int = 4
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    cost_cap_usd: float | None = None
    notes: str = ""
    created_at: datetime | None = None
    prompt_caching: bool = False
    json_mode: Literal["json_object", "json_schema"] | None = None
    require_parameters: bool = False
    extra_headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("api_key_env")
    @classmethod
    def validate_env_name(cls, value: str) -> str:
        """Require a valid uppercase environment variable name."""

        if _ENV_NAME_RE.fullmatch(value) is None:
            raise ValueError("api_key_env must match ^[A-Z][A-Z0-9_]+$")
        return value

    @model_validator(mode="after")
    def validate_per_sdk_kind(self) -> ProviderProfile:
        """Apply provider-specific guards from the PRD amendments."""

        if not _is_allowed_base_url(self.base_url):
            raise ValueError("base_url must be HTTPS or http://localhost for local providers")
        if self.sdk_kind == "openai-compat" and self.json_mode is None:
            raise ValueError("openai-compat profiles require json_mode")
        if _is_deepseek_url(self.base_url) and self.json_mode == "json_schema":
            raise ValueError("DeepSeek (api.deepseek.com) does not support json_schema; use json_object")
        return self


class ProfilesConfig(BaseModel):
    """Persistent profiles.toml model."""

    schema_version: int = 1
    active: str | None = None
    profiles: dict[str, ProviderProfile] = Field(default_factory=dict)


def load_profiles() -> ProfilesConfig:
    """Read profiles.toml and reject literal secret fields before validation."""

    profile_path = paths.profiles_toml_path()
    if not profile_path.exists():
        return ProfilesConfig()
    with profile_path.open("rb") as handle:
        raw = tomllib.load(handle)
    _reject_literal_key_fields(raw)
    return ProfilesConfig.model_validate(_normalize_profiles_dict(raw))


def save_profiles(cfg: ProfilesConfig) -> None:
    """Persist profiles.toml without writing API key values."""

    profile_path = paths.profiles_toml_path()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(tomli_w.dumps(_to_toml_dict(cfg)), encoding="utf-8")


def write_env_var(env_path: Path, var_name: str, value: str) -> None:
    """Write or update ``var_name=value`` in a dotenv file.

    Existing variables and comments are preserved. The target file is created
    with owner-only permissions where the platform exposes a reliable control:
    POSIX ``0600`` and a best-effort Windows ACL restriction via ``icacls``.
    API key values are deliberately never logged.
    """

    if _ENV_NAME_RE.fullmatch(var_name) is None:
        raise ValueError("var_name must match ^[A-Z][A-Z0-9_]+$")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    rendered = f"{var_name}={_dotenv_quote(value)}"
    updated = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key == var_name:
            if not updated:
                new_lines.append(rendered)
                updated = True
            continue
        new_lines.append(line)
    if not updated:
        new_lines.append(rendered)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    _restrict_env_file_permissions(env_path)


def get_active_profile(cfg: ProfilesConfig) -> ProviderProfile:
    """Return the active profile or raise when none is selected."""

    if cfg.active is None:
        raise ProfileValidationError("No active profile configured.")
    try:
        return cfg.profiles[cfg.active]
    except KeyError as exc:
        raise ProfileValidationError(f"Active profile {cfg.active!r} does not exist.") from exc


def resolve_api_key(profile: ProviderProfile) -> str:
    """Load the API key for a profile from profiles/.env after permission checks."""

    env_path = paths.profiles_env_path()
    ok, message = paths.check_env_permissions(env_path)
    if not ok:
        raise ProfileMissingKeyError(
            profile.name,
            profile.api_key_env,
            f"profiles/.env exists but has world-readable permissions. {message}",
        )
    values = dotenv_values(env_path)
    key = values.get(profile.api_key_env)
    log.info("Resolved API key reference %s for profile %s", profile.api_key_env, profile.name)
    if not key:
        raise ProfileMissingKeyError(profile.name, profile.api_key_env)
    return str(key)


def _dotenv_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./~\-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def _restrict_env_file_permissions(env_path: Path) -> None:
    if os.name != "nt":
        env_path.chmod(0o600)
        return
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    username = os.environ.get("USERNAME")
    if not username:
        return
    # Best effort: protect the key store for normal NTFS paths without failing
    # tests or portable filesystems that do not expose Windows ACLs.
    try:
        subprocess.run(
            ["icacls", str(env_path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _is_allowed_base_url(value: str) -> bool:
    return value.startswith("https://") or value.startswith("http://localhost") or value.startswith(
        "http://127.0.0.1"
    )


def _is_deepseek_url(value: str) -> bool:
    return "api.deepseek.com" in value.casefold()


def _reject_literal_key_fields(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key).casefold() in _LITERAL_SECRET_FIELDS and isinstance(item, str):
                raise ProfileValidationError(
                    "Profile contains what appears to be a literal API key. API keys belong in "
                    "profiles/.env, referenced by api_key_env."
                )
            _reject_literal_key_fields(item, child_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_literal_key_fields(item, f"{path}[{index}]")


def _normalize_profiles_dict(raw: dict[str, Any]) -> dict[str, Any]:
    active_raw = raw.get("active")
    active = active_raw
    if isinstance(active_raw, dict):
        active = active_raw.get("profile")
    profiles: dict[str, Any] = {}
    for name, profile_raw in (raw.get("profiles") or {}).items():
        if isinstance(profile_raw, dict):
            profiles[str(name)] = {"name": str(name), **profile_raw}
    return {
        "schema_version": raw.get("schema_version", 1),
        "active": active,
        "profiles": profiles,
    }


def _to_toml_dict(cfg: ProfilesConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": cfg.schema_version}
    if cfg.active is not None:
        payload["active"] = {"profile": cfg.active}
    payload["profiles"] = {
        name: profile.model_dump(mode="python", exclude={"name"}, exclude_none=True)
        for name, profile in sorted(cfg.profiles.items())
    }
    return payload


__all__ = [
    "ProfileMissingKeyError",
    "ProfileValidationError",
    "ProfilesConfig",
    "ProviderProfile",
    "get_active_profile",
    "load_profiles",
    "resolve_api_key",
    "save_profiles",
    "write_env_var",
]
