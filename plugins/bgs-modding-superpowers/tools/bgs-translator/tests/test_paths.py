"""Tests for persistent path resolution."""

from __future__ import annotations

from pathlib import Path


def test_home_default(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config import paths

    monkeypatch.delenv("BGS_MODDING_SUPERPOWERS_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert paths.home() == (tmp_path / ".bgs-modding-superpowers").resolve()


def test_home_env_override(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config import paths

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    assert paths.home() == tmp_path.resolve()


def test_home_creates_dir(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config import paths

    root = tmp_path / "vault"
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(root))

    assert paths.home().exists()
    assert paths.home().is_dir()


def test_subroot_creates(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config import paths

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    kb_root = paths.kb_root()

    assert kb_root == tmp_path / "kb"
    assert kb_root.exists()
    assert paths.kb_packs_root().exists()
    assert paths.translator_root().exists()
    assert paths.config_root().exists()


def test_paths_isolation(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config import paths

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    project = paths.project_root("test")

    assert project == tmp_path / "translator" / "projects" / "test"
    assert not project.exists()
