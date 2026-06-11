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

MASTER_GAME_HINTS: dict[str, str] = {
    "starfield.esm": "Starfield",
    "fallout4.esm": "Fallout4",
    "fallout76.esm": "Fallout76",
    "skyrim.esm": "SkyrimSE",
    "oblivion.esm": "Oblivion",
    "falloutnv.esm": "FalloutNV",
    "fallout3.esm": "Fallout3",
}


def detect_game_from_form_version(fv: int) -> list[str]:
    """Return candidate games whose known ranges contain ``fv``."""

    return [entry.game for entry in KNOWN_RANGES if entry.low <= fv <= entry.high]


def detect_game_from_masters(masters: list[str]) -> list[str]:
    """Return candidate games from root master filenames."""

    candidates: list[str] = []
    seen: set[str] = set()
    for master in masters:
        game = MASTER_GAME_HINTS.get(master.casefold())
        if game and game not in seen:
            seen.add(game)
            candidates.append(game)
    return candidates


def detect_game_from_header(form_version: int, masters: list[str]) -> list[str]:
    """Return game candidates using root masters first, then form version."""

    master_candidates = detect_game_from_masters(masters)
    if master_candidates:
        return master_candidates
    return detect_game_from_form_version(form_version)


def is_tes4_header_signature(sig: bytes) -> bool:
    """Return true when ``sig`` is the TES4-family header record signature."""

    return sig == b"TES4"


__all__ = [
    "KNOWN_RANGES",
    "MASTER_GAME_HINTS",
    "FormVersionRange",
    "detect_game_from_form_version",
    "detect_game_from_header",
    "detect_game_from_masters",
    "is_tes4_header_signature",
]
