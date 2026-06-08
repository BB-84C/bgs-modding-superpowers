"""Tests for the Profiles tab API-key write path."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def test_write_env_var_creates_secure_env_file(tmp_path: Path) -> None:
    from bgs_translator.config.profiles import write_env_var

    env_path = tmp_path / ".env"

    write_env_var(env_path, "BGS_TRANSLATOR_KEY_OPENAI", "sk-test")

    assert env_path.read_text(encoding="utf-8") == "BGS_TRANSLATOR_KEY_OPENAI=sk-test\n"
    if os.name != "nt":
        assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_write_env_var_preserves_other_values_and_updates_target(tmp_path: Path) -> None:
    from bgs_translator.config.profiles import write_env_var

    env_path = tmp_path / ".env"
    env_path.write_text("OTHER=keep\nBGS_TRANSLATOR_KEY_OPENAI=old\n", encoding="utf-8")
    if os.name != "nt":
        env_path.chmod(0o600)

    write_env_var(env_path, "BGS_TRANSLATOR_KEY_OPENAI", "new value")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    assert "OTHER=keep" in lines
    assert "BGS_TRANSLATOR_KEY_OPENAI='new value'" in lines
    assert "BGS_TRANSLATOR_KEY_OPENAI=old" not in lines
