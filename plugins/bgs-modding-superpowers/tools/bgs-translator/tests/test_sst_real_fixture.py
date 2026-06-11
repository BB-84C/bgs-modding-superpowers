"""Smoke-load real Starfield SST fixtures from a local xTranslator install.

These tests run only when the canonical xTranslator User Dictionaries path is
present; they're skipped otherwise so CI machines without the local Starfield
install stay green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bgs_translator.sst.hash import compute_rhash
from bgs_translator.sst.reader import read_sst

_FIXTURE_ROOT = Path(
    r"D:\SteamLibrary\steamapps\common\Starfield\Tools"
    r"\xTranslator-313-1-4-5-alpha-1694868294\_xTranslator\UserDictionaries\Starfield"
)

_SMALL_FIXTURE = _FIXTURE_ROOT / "srb_showreadbooks_en_zhhans.sst"


def _have_fixture(path: Path) -> bool:
    return path.exists() and path.is_file()


@pytest.mark.skipif(
    not _have_fixture(_SMALL_FIXTURE),
    reason=f"xTranslator fixture not present at {_SMALL_FIXTURE}",
)
def test_smoke_load_small_fixture() -> None:
    parsed = read_sst(_SMALL_FIXTURE)
    # 354-byte spike fixture is documented in docs/spikes/spike-findings.md §2.
    assert parsed.version == 8
    assert parsed.label == "SSU9"
    # Spike documented 3 masters.
    assert parsed.masters == [
        "starfield.esm",
        "blueprintships-starfield.esm",
        "srb_showreadbooks.esm",
    ]
    assert parsed.colab_labels == []
    # Spike documented 3 entries.
    assert len(parsed.entries) == 3


@pytest.mark.skipif(
    not _have_fixture(_SMALL_FIXTURE),
    reason=f"xTranslator fixture not present at {_SMALL_FIXTURE}",
)
def test_small_fixture_perk_entries_share_rhash() -> None:
    parsed = read_sst(_SMALL_FIXTURE)
    perks = [e for e in parsed.entries if e.signature == "PERK" and e.field == "EPF2"]
    assert len(perks) == 2
    # Both PERK:EPF2 entries share an EditorID → identical rHash.
    assert perks[0].rhash == perks[1].rhash == 0xEFF18B6A


@pytest.mark.skipif(
    not _have_fixture(_SMALL_FIXTURE),
    reason=f"xTranslator fixture not present at {_SMALL_FIXTURE}",
)
def test_small_fixture_tes4_header_rhash_matches_no_edid_formula() -> None:
    parsed = read_sst(_SMALL_FIXTURE)
    tes4 = next(e for e in parsed.entries if e.signature == "TES4")
    # TES4 record has no EditorID; rHash = stringHash('[00000000]').
    assert tes4.formid == 0
    assert tes4.rhash == compute_rhash(None, 0)
    assert tes4.rhash == 0xEF7C96E5  # observed value


@pytest.mark.skipif(
    not _have_fixture(_FIXTURE_ROOT),
    reason=f"xTranslator fixture root not present at {_FIXTURE_ROOT}",
)
def test_smoke_load_several_real_dictionaries() -> None:
    # Load a handful of size-diverse fixtures and assert no exceptions plus
    # version recognition. We cap on size so the test doesn't drag huge dicts.
    candidates = sorted(_FIXTURE_ROOT.glob("*.sst"), key=lambda p: p.stat().st_size)
    sample = [p for p in candidates if p.stat().st_size < 200_000][:8]
    if not sample:
        pytest.skip("no small enough fixtures to sample")
    for path in sample:
        parsed = read_sst(path)
        assert parsed.version in {1, 2, 3, 4, 5, 6, 7, 8}, path
        # Real fixtures should always have ≥1 entry.
        assert parsed.entries, path
