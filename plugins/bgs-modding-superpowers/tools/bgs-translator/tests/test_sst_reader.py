"""Reader tests: round-trip + version handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from bgs_translator.sst.hash import compute_rhash
from bgs_translator.sst.reader import read_sst
from bgs_translator.sst.status import SStrParam
from bgs_translator.sst.writer import SSTUnit, write_sst


def _unit(**overrides: object) -> SSTUnit:
    base: dict[str, object] = {
        "list_index": 0,
        "strid": 0,
        "formid": 0x02000800,
        "signature": "PERK",
        "field": "EPF2",
        "index": 0,
        "index_max": 1,
        "rhash": compute_rhash("PerkEdid01", 0x02000800),
        "colab_id": 0,
        "s_params": int(SStrParam.TRANSLATED),
        "source": "Take Book",
        "dest": "拿书",
    }
    base.update(overrides)
    return SSTUnit(**base)  # type: ignore[arg-type]


def test_round_trip_empty(tmp_path: Path) -> None:
    out = tmp_path / "empty.sst"
    write_sst(out, [], masters=[])
    parsed = read_sst(out)
    assert parsed.version == 8
    assert parsed.label == "SSU9"
    assert parsed.masters == []
    assert parsed.colab_labels == []
    assert parsed.entries == []


def test_round_trip_single_entry(tmp_path: Path) -> None:
    out = tmp_path / "one.sst"
    original = _unit()
    write_sst(out, [original], masters=["starfield.esm"])
    parsed = read_sst(out)
    assert parsed.version == 8
    assert parsed.masters == ["starfield.esm"]
    assert len(parsed.entries) == 1
    e = parsed.entries[0]
    assert e.list_index == original.list_index
    assert e.formid == original.formid
    assert e.signature == "PERK"
    assert e.field == "EPF2"
    assert e.index == original.index
    assert e.index_max == original.index_max
    assert e.rhash == original.rhash
    assert e.colab_id == original.colab_id
    assert e.s_params == original.s_params
    assert e.source == original.source
    assert e.dest == original.dest


def test_round_trip_multiple_entries(tmp_path: Path) -> None:
    out = tmp_path / "many.sst"
    units = [
        _unit(source=f"Source {i}", dest=f"翻译{i}", index=i, list_index=i % 3)
        for i in range(7)
    ]
    write_sst(
        out,
        units,
        masters=["starfield.esm", "extension.esm"],
        colab_labels=[(1, "team-alpha")],
    )
    parsed = read_sst(out)
    assert parsed.masters == ["starfield.esm", "extension.esm"]
    assert parsed.colab_labels == [(1, "team-alpha")]
    assert len(parsed.entries) == len(units)
    for original, decoded in zip(units, parsed.entries, strict=True):
        assert decoded.source == original.source
        assert decoded.dest == original.dest
        assert decoded.index == original.index
        assert decoded.list_index == original.list_index


def test_round_trip_validated_is_stripped(tmp_path: Path) -> None:
    # Writer drops VALIDATED before persisting; reader sees it as absent.
    out = tmp_path / "validated.sst"
    write_sst(
        out,
        [_unit(s_params=int(SStrParam.TRANSLATED | SStrParam.VALIDATED))],
        masters=[],
    )
    parsed = read_sst(out)
    assert parsed.entries[0].s_params == int(SStrParam.TRANSLATED)


def test_round_trip_ssu8_drops_master_list(tmp_path: Path) -> None:
    out = tmp_path / "ssu8.sst"
    write_sst(
        out,
        [_unit()],
        masters=["never.esm"],
        colab_labels=[(7, "seven")],
        sst_version="SSU8",
    )
    parsed = read_sst(out)
    assert parsed.version == 7
    assert parsed.label == "SSU8"
    # SSU8 has no master section, so the writer must have dropped it.
    assert parsed.masters == []
    assert parsed.colab_labels == [(7, "seven")]
    assert len(parsed.entries) == 1


def test_reader_rejects_unknown_magic(tmp_path: Path) -> None:
    out = tmp_path / "bad.sst"
    out.write_bytes(b"XXXX\x00")
    with pytest.raises(ValueError):
        read_sst(out)


def test_reader_unicode_dest(tmp_path: Path) -> None:
    out = tmp_path / "cn.sst"
    long_text = "拿书" * 50
    write_sst(out, [_unit(dest=long_text)], masters=[])
    parsed = read_sst(out)
    assert parsed.entries[0].dest == long_text
