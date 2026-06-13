import struct
from pathlib import Path

import pytest

from mo2_assets_engine.archives.bsa import BSAArchive, BSAVersion


def test_bsa_v105_reader_lists_all_members(synthetic_bsa_v105: Path) -> None:
    archive = BSAArchive.open(synthetic_bsa_v105)
    assert archive.version is BSAVersion.V105
    names = sorted(archive.list_member_names())
    assert names == [
        "meshes/test/bar.nif",
        "meshes/test/foo.nif",
        "textures/test/bar.dds",
        "textures/test/foo.dds",
    ]


def test_bsa_open_raises_on_bad_magic(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-bsa.bsa"
    bogus.write_bytes(b"NOPE" + b"\x00" * 32)
    with pytest.raises(ValueError, match="Not a BSA archive"):
        BSAArchive.open(bogus)


def test_bsa_open_raises_on_unsupported_version(tmp_path: Path) -> None:
    bogus = tmp_path / "old-bsa.bsa"
    bogus.write_bytes(struct.pack("<4sI", b"BSA\x00", 999) + b"\x00" * 28)
    with pytest.raises(ValueError, match="Unsupported BSA version"):
        BSAArchive.open(bogus)
