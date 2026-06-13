from pathlib import Path

import pytest

from mo2_assets_engine.archives.ba2 import BA2Archive, BA2Kind


def test_ba2_gnrl_reader_lists_all_members(synthetic_ba2_gnrl: Path) -> None:
    archive = BA2Archive.open(synthetic_ba2_gnrl)
    assert archive.kind is BA2Kind.GNRL
    names = archive.list_member_names()
    assert sorted(names) == [
        "materials/test/foo.bgsm",
        "scripts/source/user/test.psc",
        "strings/test_en.strings",
    ]


def test_ba2_gnrl_reader_normalizes_separators(synthetic_ba2_gnrl: Path) -> None:
    archive = BA2Archive.open(synthetic_ba2_gnrl)
    for name in archive.list_member_names():
        assert "\\" not in name


def test_ba2_dx10_reader_lists_all_members(synthetic_ba2_dx10: Path) -> None:
    archive = BA2Archive.open(synthetic_ba2_dx10)
    assert archive.kind is BA2Kind.DX10
    names = archive.list_member_names()
    assert sorted(names) == [
        "textures/test/bar.dds",
        "textures/test/foo.dds",
    ]


def test_ba2_open_raises_on_non_btdx(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-ba2.ba2"
    bogus.write_bytes(b"NOT-A-BA2" + b"\x00" * 32)
    with pytest.raises(ValueError, match="Not a BA2 archive"):
        BA2Archive.open(bogus)
