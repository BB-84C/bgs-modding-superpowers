"""Game detection from TES4 header form-version metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormVersionRange:
    """Known inclusive form-version range for a TES4-family game."""

    game: str
    low: int
    high: int


KNOWN_RANGES: list[FormVersionRange] = [
    FormVersionRange("SkyrimLE", 43, 43),
    FormVersionRange("SkyrimSE", 43, 44),
    FormVersionRange("Fallout4", 131, 131),
    FormVersionRange("Fallout76", 131, 250),
    FormVersionRange("Starfield", 552, 576),
]


def detect_game_from_form_version(fv: int) -> list[str]:
    """Return candidate games whose known ranges contain ``fv``."""

    return [entry.game for entry in KNOWN_RANGES if entry.low <= fv <= entry.high]


def is_tes4_header_signature(sig: bytes) -> bool:
    """Return true when ``sig`` is the TES4-family header record signature."""

    return sig == b"TES4"


__all__ = [
    "KNOWN_RANGES",
    "FormVersionRange",
    "detect_game_from_form_version",
    "is_tes4_header_signature",
]
