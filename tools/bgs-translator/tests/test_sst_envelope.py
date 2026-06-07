"""Magic constants and version detection for the SST envelope."""

from __future__ import annotations

import pytest

from bgs_translator.sst.envelope import (
    SST_MAGIC_TO_VERSION,
    SST_VERSION_LABELS,
    SST_VERSION_TO_MAGIC,
    SSU2,
    SSU3,
    SSU4,
    SSU5,
    SSU6,
    SSU7,
    SSU8,
    SSU9,
    SSTVersion,
    detect_label,
    detect_version,
    label_for_version,
    magic_for_label,
)


def test_magic_constants_match_pascal_source() -> None:
    # Pascal TESVT_Const.pas: $32555353..$39555353
    assert SSU2 == 0x32555353
    assert SSU3 == 0x33555353
    assert SSU4 == 0x34555353
    assert SSU5 == 0x35555353
    assert SSU6 == 0x36555353
    assert SSU7 == 0x37555353
    assert SSU8 == 0x38555353
    assert SSU9 == 0x39555353


def test_magic_bytes_are_ascii_when_little_endian() -> None:
    # Little-endian on disk = "SSU<digit>" ASCII
    assert SSU9.to_bytes(4, "little") == b"SSU9"
    assert SSU2.to_bytes(4, "little") == b"SSU2"


def test_detect_version_known_magics() -> None:
    for magic, version in SST_MAGIC_TO_VERSION.items():
        buf = magic.to_bytes(4, "little") + b"\x00\x00"
        assert detect_version(buf) == version


def test_detect_version_returns_zero_for_unknown() -> None:
    assert detect_version(b"XXXX") == 0
    assert detect_version(b"") == 0
    assert detect_version(b"SS") == 0  # too short


def test_detect_label_round_trip() -> None:
    assert detect_label(SSU9.to_bytes(4, "little")) == "SSU9"
    assert detect_label(SSU8.to_bytes(4, "little")) == "SSU8"
    assert detect_label(b"junk") is None


def test_label_for_version_round_trip() -> None:
    for version, label in SST_VERSION_LABELS.items():
        assert label_for_version(version) == label
        assert magic_for_label(label) == SST_VERSION_TO_MAGIC[version]


def test_label_for_unknown_version_raises() -> None:
    with pytest.raises(ValueError):
        label_for_version(99)
    with pytest.raises(ValueError):
        magic_for_label("SSU10")


def test_sst_version_enum_aligns_with_mapping() -> None:
    assert SSTVersion.V8_SSU9.value == 8
    assert SSTVersion.UNKNOWN.value == 0
    assert SSTVersion.V1_SSU2.value == SST_MAGIC_TO_VERSION[SSU2]
