"""Path resolution for bgs-translator persistent state.

The unified root is ~/.bgs-modding-superpowers/, overridable via
BGS_MODDING_SUPERPOWERS_HOME env var. All subpath helpers create
directories on demand.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def home() -> Path:
    """Return the resolved bgs-modding-superpowers root, creating it if needed."""
    override = os.environ.get("BGS_MODDING_SUPERPOWERS_HOME")
    root = (
        Path(override).expanduser()
        if override and override.strip()
        else Path.home() / ".bgs-modding-superpowers"
    )
    return _ensure_dir(root.resolve())


def kb_root() -> Path:
    """Return the KB cache root, creating it if needed."""
    return _ensure_dir(home() / "kb")


def kb_packs_root() -> Path:
    """Return the installed KB packs root, creating it if needed."""
    return _ensure_dir(kb_root() / "packs")


def kb_user_packs_root() -> Path:
    """Return the user KB packs root, honoring BGS_KB_USER_PACKS when set."""
    override = os.environ.get("BGS_KB_USER_PACKS")
    root = Path(override).expanduser() if override and override.strip() else kb_root() / "user-packs"
    return _ensure_dir(root.resolve())


def translator_root() -> Path:
    """Return the translator state root, creating it if needed."""
    return _ensure_dir(home() / "translator")


def projects_root() -> Path:
    """Return the translator projects root, creating it if needed."""
    return _ensure_dir(translator_root() / "projects")


def project_root(name: str) -> Path:
    """Return a named project root without creating it."""
    return projects_root() / name


def profiles_root() -> Path:
    """Return the provider profiles root, creating it if needed."""
    return _ensure_dir(translator_root() / "profiles")


def profiles_env_path() -> Path:
    """Return the provider profiles .env path without creating it."""
    return profiles_root() / ".env"


def profiles_toml_path() -> Path:
    """Return the provider profiles TOML path without creating it."""
    return profiles_root() / "profiles.toml"


def config_root() -> Path:
    """Return the global config root, creating it if needed."""
    return _ensure_dir(translator_root() / "config")


def settings_path() -> Path:
    """Return the global settings TOML path without creating it."""
    return config_root() / "settings.toml"


def pricing_path() -> Path:
    """Return the pricing TOML path without creating it."""
    return config_root() / "pricing.toml"


def prompt_templates_root() -> Path:
    """Return the prompt templates root, creating it if needed."""
    return _ensure_dir(config_root() / "prompt-templates")


def logs_root() -> Path:
    """Return the translator logs root, creating it if needed."""
    return _ensure_dir(translator_root() / "logs")


def check_env_permissions(env_path: Path) -> tuple[bool, str]:
    """Check that a provider .env file is not world-readable where reliable."""
    if not env_path.exists():
        return True, "file does not exist; no permission check needed"

    if os.name == "nt":
        return True, "permission check skipped on Windows"

    mode = stat.S_IMODE(env_path.stat().st_mode)
    if mode != 0o600:
        return False, f"Insecure permissions: {mode:#04o}. Run: chmod 600 {env_path}"

    return True, "permissions are secure"


__all__ = [
    "check_env_permissions",
    "config_root",
    "home",
    "kb_packs_root",
    "kb_root",
    "kb_user_packs_root",
    "logs_root",
    "pricing_path",
    "profiles_env_path",
    "profiles_root",
    "profiles_toml_path",
    "project_root",
    "projects_root",
    "prompt_templates_root",
    "settings_path",
    "translator_root",
]
