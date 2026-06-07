"""Tests for KB cache migration."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_detect_legacy_returns_none_when_clean(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.migrations import detect_legacy_bgs_kb_cache


    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")

    assert detect_legacy_bgs_kb_cache() is None


def test_detect_legacy_returns_path_when_present(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.migrations import detect_legacy_bgs_kb_cache

    user_home = tmp_path / "user"
    legacy = user_home / ".cache" / "bgs-kb"
    (legacy / "packs").mkdir(parents=True)
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path / "new-home"))
    monkeypatch.setattr(Path, "home", lambda: user_home)

    assert detect_legacy_bgs_kb_cache() == legacy


def test_migration_needed_skips_when_setting_set(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.migrations import migration_needed
    from bgs_translator.config.settings import BehaviorSettings, Settings, save_settings

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    save_settings(Settings(behavior=BehaviorSettings(skip_kb_migration=True)))

    needed, legacy, reason = migration_needed()

    assert needed is False
    assert legacy is None
    assert "skipped" in reason.lower()


def test_migrate_kb_cache_moves_files(tmp_path) -> None:
    from bgs_translator.config.migrations import migrate_kb_cache

    legacy = tmp_path / "legacy-bgs-kb"
    target = tmp_path / "new" / "kb"
    (legacy / "packs" / "bgs-kb-core").mkdir(parents=True)
    (legacy / "manifest-index.json").write_text("{}")

    migrate_kb_cache(legacy, target, create_symlink=False)

    assert not legacy.exists()
    assert (target / "packs" / "bgs-kb-core").exists()
    assert (target / "manifest-index.json").read_text() == "{}"


def test_migrate_kb_cache_refuses_overwrite(tmp_path) -> None:
    from bgs_translator.config.migrations import migrate_kb_cache

    legacy = tmp_path / "legacy-bgs-kb"
    target = tmp_path / "new" / "kb"
    (legacy / "packs").mkdir(parents=True)
    target.mkdir(parents=True)
    (target / "already.txt").write_text("occupied")

    with pytest.raises(FileExistsError):
        migrate_kb_cache(legacy, target, create_symlink=False)
