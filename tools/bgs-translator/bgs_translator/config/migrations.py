"""KB cache migration: ~/.local/share/... → ~/.bgs-modding-superpowers/kb/.

The bgs-kb MCP server has historically cached packs in various locations
depending on install method. This module detects legacy locations and
offers to migrate. Per AMENDMENTS, this migration is opt-in via prompt;
skip-migration honored via Settings.behavior.skip_kb_migration.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

import typer

from bgs_translator.config import paths
from bgs_translator.config.settings import load_settings

log = logging.getLogger(__name__)


def _legacy_candidates() -> list[Path]:
    user_home = Path.home()
    return [
        user_home / ".cache" / "bgs-kb",
        user_home / ".local" / "share" / "bgs-kb",
        user_home / "AppData" / "Local" / "bgs-kb",
        user_home / "AppData" / "Roaming" / "bgs-kb",
        user_home / "Library" / "Application Support" / "bgs-kb",
        user_home / ".bgs-kb",
    ]


def detect_legacy_bgs_kb_cache() -> Path | None:
    """Return the first legacy bgs-kb cache that contains packs/."""
    target = paths.kb_root().resolve()
    for candidate in _legacy_candidates():
        resolved = candidate.resolve()
        if resolved == target:
            continue
        if candidate.exists() and (candidate / "packs").is_dir():
            return candidate
    return None


def _has_content(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def migration_needed() -> tuple[bool, Path | None, str]:
    """Return whether a legacy cache should be offered for migration."""
    settings = load_settings()
    if settings.behavior.skip_kb_migration:
        return False, None, "KB cache migration skipped by settings."

    target = paths.kb_root()
    if _has_content(target):
        return False, None, f"KB root already has content at {target}."

    legacy = detect_legacy_bgs_kb_cache()
    if legacy is None:
        return False, None, "No legacy bgs-kb cache detected."

    return True, legacy, f"Legacy bgs-kb cache detected at {legacy}."


def _create_compat_link(old_location: Path, new_location: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(old_location), str(new_location)],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    old_location.symlink_to(new_location, target_is_directory=True)


def migrate_kb_cache(legacy: Path, target: Path, *, create_symlink: bool = True) -> None:
    """Move a legacy bgs-kb cache to the unified target root."""
    if not legacy.exists():
        raise FileNotFoundError(f"Legacy KB cache does not exist: {legacy}")
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty KB cache target: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.rmdir()

    try:
        shutil.move(str(legacy), str(target))
    except Exception as exc:
        if target.exists() and not legacy.exists():
            shutil.move(str(target), str(legacy))
        raise RuntimeError(
            "Failed to migrate bgs-kb cache. Remediation: ensure both locations are writable, "
            f"then manually move '{legacy}' to '{target}'. Original error: {exc}"
        ) from exc

    if create_symlink:
        try:
            _create_compat_link(legacy, target)
        except Exception as exc:
            log.warning(
                "Could not create compatibility symlink at %s. Older bgs-kb invocations may fail: %s",
                legacy,
                exc,
            )


def prompt_user_for_migration_cli(legacy: Path, target: Path) -> bool:
    """Prompt the user to opt into KB cache migration."""
    typer.echo("Legacy bgs-kb cache detected at:")
    typer.echo(f"    {legacy}")
    typer.echo("")
    typer.echo("This tool now expects KB cache at:")
    typer.echo(f"    {target}")
    typer.echo("")
    return typer.confirm("Migrate now?", default=True)


__all__ = [
    "detect_legacy_bgs_kb_cache",
    "migrate_kb_cache",
    "migration_needed",
    "prompt_user_for_migration_cli",
]
