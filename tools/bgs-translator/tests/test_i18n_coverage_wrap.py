"""Regression checks for Chunk L.2 i18n wrapping."""

from __future__ import annotations

from pathlib import Path

EXPECTED_MSGIDS = {
    "Name",
    "SDK kind",
    "Base URL",
    "Model",
    "Concurrency",
    "Cost cap",
    "API key env",
    "Prompt caching",
    "JSON mode",
    "Notes",
    "[ NO PROJECT LOADED ]",
    "Select a project from the nav tree",
    "[ NO LOGS RECORDED ]",
    "Today's JSONL is empty",
    "[ NO DATA LOADED ]",
    "VAULT-TEC INDUSTRIES",
    "Show",
    "Hide",
    "Pause tail",
    "Resume tail",
    "Open logs folder",
    "Add glossary entry",
}


def _read_po_msgids(path: Path) -> set[str]:
    return {
        line.split(" ", 1)[1].strip().strip('"')
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("msgid ")
    }


def test_catalogs_include_chunk_l2_msgids() -> None:
    root = Path(__file__).resolve().parents[1]
    en_ids = _read_po_msgids(root / "bgs_translator" / "gui" / "i18n" / "en.po")
    zh_ids = _read_po_msgids(root / "bgs_translator" / "gui" / "i18n" / "zh_CN.po")
    assert EXPECTED_MSGIDS <= en_ids
    assert EXPECTED_MSGIDS <= zh_ids


def test_known_hardcoded_sites_are_wrapped() -> None:
    root = Path(__file__).resolve().parents[1]
    project_tab = (root / "bgs_translator" / "gui" / "tabs" / "project_tab.py").read_text(encoding="utf-8")
    profiles_tab = (root / "bgs_translator" / "gui" / "tabs" / "profiles_tab.py").read_text(encoding="utf-8")
    logs_tab = (root / "bgs_translator" / "gui" / "tabs" / "logs_tab.py").read_text(encoding="utf-8")
    assert '(_("Project"), "project_name")' in project_tab
    assert 'caption=_("[ NO PROJECT LOADED ]")' in project_tab
    assert '(_("Name"), "name")' in profiles_tab
    assert '_(" (active)")' in profiles_tab
    assert '_("all")' in logs_tab and '_("debug")' in logs_tab
