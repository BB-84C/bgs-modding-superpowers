"""Tests for TES4-family form-version detection."""

from __future__ import annotations


def test_skyrim_se_detection() -> None:
    from bgs_translator.parsers.form_versions import detect_game_from_form_version

    assert detect_game_from_form_version(43) == ["SkyrimLE", "SkyrimSE"]


def test_fv44() -> None:
    from bgs_translator.parsers.form_versions import detect_game_from_form_version

    assert detect_game_from_form_version(44) == ["SkyrimSE"]


def test_starfield() -> None:
    from bgs_translator.parsers.form_versions import detect_game_from_form_version

    assert detect_game_from_form_version(560) == ["Starfield"]


def test_unknown() -> None:
    from bgs_translator.parsers.form_versions import detect_game_from_form_version

    assert detect_game_from_form_version(999) == []
