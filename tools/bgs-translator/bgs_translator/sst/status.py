"""SST ``sStrParams`` bitset semantics, byte (de)serialization, and UI colors.

Provenance: ``TESVT_typedef.pas:91-100`` (sStrParam enum), ``TESVT_SSTFunc.pas:
SaveSSTFile`` (``tmpParams := sk.sparams - [validated];`` strips ``VALIDATED``
before persistence).

The Pascal type is ``set of sStrParam`` over 8 elements, which Delphi packs
into a single byte. That confirms the 1-byte width vs. the original PRD's
4-byte hedge (cf. ``docs/plans/translator-tool/AMENDMENTS.md`` §2.5).
"""

from __future__ import annotations

from enum import IntFlag

__all__ = [
    "DEFAULT_UI_COLOR",
    "STATUS_PRIORITY",
    "SStrParam",
    "from_byte",
    "to_byte",
    "ui_color",
]


class SStrParam(IntFlag):
    """Single-byte status bitset persisted in each SST entry.

    Bit order mirrors the Pascal ``sStrParam`` ordinals 0..7.
    """

    NONE = 0
    TRANSLATED = 1 << 0
    LOCKED_TRANS = 1 << 1
    INCOMPLETE_TRANS = 1 << 2
    VALIDATED = 1 << 3
    DEPRECATED_PARAM1 = 1 << 4
    DEPRECATED_PARAM2 = 1 << 5
    OLD_DATA = 1 << 6
    PENDING = 1 << 7


# Persistence policy: ``validated`` is a UI-only confirmation. xTranslator's
# writer explicitly strips it before serialization.
_PERSIST_MASK: int = 0xFF & ~int(SStrParam.VALIDATED)


# UI color names. Priority is highest-first; the first matching flag wins.
# Order taken from the PRD §1.5 table (`yellow > pink > blue > gray > white`)
# with ``pending`` placed above ``locked`` because it overrides the default
# "translated" state in the GUI (orange-ish "pending" tint).
STATUS_PRIORITY: tuple[tuple[SStrParam, str], ...] = (
    (SStrParam.PENDING, "orange"),
    (SStrParam.LOCKED_TRANS, "yellow"),
    (SStrParam.INCOMPLETE_TRANS, "pink"),
    (SStrParam.VALIDATED, "blue"),
    (SStrParam.OLD_DATA, "gray"),
    (SStrParam.TRANSLATED, "white"),
)

DEFAULT_UI_COLOR: str = "default"


def to_byte(params: SStrParam | int) -> int:
    """Serialize sParams to the 1-byte on-disk representation.

    The ``validated`` flag is stripped per xTranslator's ``SaveSSTFile`` rule
    (``tmpParams := sk.sparams - [validated]``).
    """
    return int(params) & _PERSIST_MASK


def from_byte(value: int) -> SStrParam:
    """Decode the 1-byte on-disk representation into a typed flag set."""
    if not 0 <= value <= 0xFF:
        raise ValueError(f"sParams byte out of range: {value!r}")
    return SStrParam(value)


def ui_color(params: SStrParam | int) -> str:
    """Pick the UI color name that xTranslator would paint a row with these flags."""
    p = SStrParam(int(params) & 0xFF)
    for flag, color in STATUS_PRIORITY:
        if flag in p:
            return color
    return DEFAULT_UI_COLOR
