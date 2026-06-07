"""SST file envelope: magic constants, internal-version mapping, and detection.

Source of truth: ``TESVT_Const.pas`` (MGuffin/xTranslator) declares the eight
``VocabUserHeader*`` cardinals and ``TESVT_SSTFunc.pas:getHeader`` maps each
magic to a small integer (1..8). The on-disk "SSU2..SSU9" label is what users
see; the internal version is what the reader's ``if version > N`` branches
key off. Both are exposed here.

All magic values are little-endian uint32 read directly off disk; the four
ASCII bytes "SSU<digit>" appear as ``0x33555353`` etc. when interpreted LE.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final, Literal

__all__ = [
    "SST_MAGIC_TO_VERSION",
    "SST_VERSION_LABELS",
    "SST_VERSION_TO_MAGIC",
    "SSU2",
    "SSU3",
    "SSU4",
    "SSU5",
    "SSU6",
    "SSU7",
    "SSU8",
    "SSU9",
    "SSTLabel",
    "SSTVersion",
    "detect_label",
    "detect_version",
    "label_for_version",
    "magic_for_label",
]


# Magic uint32 values (little-endian on disk = "SSU<digit>" ASCII).
SSU2: Final[int] = 0x32555353
SSU3: Final[int] = 0x33555353
SSU4: Final[int] = 0x34555353
SSU5: Final[int] = 0x35555353
SSU6: Final[int] = 0x36555353
SSU7: Final[int] = 0x37555353
SSU8: Final[int] = 0x38555353
SSU9: Final[int] = 0x39555353


class SSTVersion(IntEnum):
    """Internal SST version (Pascal getHeader return value).

    A value of ``0`` is the explicit "magic not recognized" sentinel; the
    reader treats anything else as a real version with ascending capability.
    """

    UNKNOWN = 0
    V1_SSU2 = 1
    V2_SSU3 = 2
    V3_SSU4 = 3
    V4_SSU5 = 4
    V5_SSU6 = 5
    V6_SSU7 = 6
    V7_SSU8 = 7
    V8_SSU9 = 8


SSTLabel = Literal["SSU2", "SSU3", "SSU4", "SSU5", "SSU6", "SSU7", "SSU8", "SSU9"]


SST_MAGIC_TO_VERSION: Final[dict[int, int]] = {
    SSU2: 1,
    SSU3: 2,
    SSU4: 3,
    SSU5: 4,
    SSU6: 5,
    SSU7: 6,
    SSU8: 7,
    SSU9: 8,
}

SST_VERSION_TO_MAGIC: Final[dict[int, int]] = {v: m for m, v in SST_MAGIC_TO_VERSION.items()}

SST_VERSION_LABELS: Final[dict[int, SSTLabel]] = {
    1: "SSU2",
    2: "SSU3",
    3: "SSU4",
    4: "SSU5",
    5: "SSU6",
    6: "SSU7",
    7: "SSU8",
    8: "SSU9",
}

_LABEL_TO_MAGIC: Final[dict[str, int]] = {
    "SSU2": SSU2,
    "SSU3": SSU3,
    "SSU4": SSU4,
    "SSU5": SSU5,
    "SSU6": SSU6,
    "SSU7": SSU7,
    "SSU8": SSU8,
    "SSU9": SSU9,
}


def detect_version(buf: bytes) -> int:
    """Return the internal version (1..8) for the magic at the start of *buf*.

    Returns ``0`` when *buf* is too short or the magic is unrecognized — the
    same sentinel ``getHeader`` uses in the Pascal source.
    """
    if len(buf) < 4:
        return 0
    magic = int.from_bytes(buf[:4], "little", signed=False)
    return SST_MAGIC_TO_VERSION.get(magic, 0)


def detect_label(buf: bytes) -> SSTLabel | None:
    """Return the on-disk label ("SSU9", ...) for *buf*, or ``None`` if unknown."""
    version = detect_version(buf)
    if version == 0:
        return None
    return SST_VERSION_LABELS[version]


def label_for_version(version: int) -> SSTLabel:
    """Return the on-disk label for a recognized internal version."""
    if version not in SST_VERSION_LABELS:
        raise ValueError(f"unknown SST internal version: {version!r}")
    return SST_VERSION_LABELS[version]


def magic_for_label(label: str) -> int:
    """Return the little-endian uint32 magic value for an on-disk label."""
    try:
        return _LABEL_TO_MAGIC[label]
    except KeyError as exc:
        raise ValueError(f"unknown SST label: {label!r}") from exc
