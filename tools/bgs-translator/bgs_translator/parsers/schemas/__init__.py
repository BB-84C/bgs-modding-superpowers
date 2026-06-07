"""Per-game parser schema registry."""

from __future__ import annotations

from bgs_translator.parsers.extractor import GameSchema

from .fnv import FNVSchema
from .fo3 import FO3Schema
from .fo4 import FO4Schema
from .fo76 import FO76Schema
from .morrowind import MorrowindSchema
from .oblivion import OblivionSchema
from .skyrim_le import SkyrimLESchema
from .skyrim_se import SkyrimSESchema
from .starfield import StarfieldSchema

_OBLIVION = OblivionSchema()
_FO3 = FO3Schema()
_FNV = FNVSchema()
_SKYRIM_LE = SkyrimLESchema()
_SKYRIM_SE = SkyrimSESchema()
_FO4 = FO4Schema()
_FO76 = FO76Schema()
_STARFIELD = StarfieldSchema()
_MORROWIND = MorrowindSchema()

SCHEMAS_BY_GAME: dict[str, GameSchema] = {
    "Oblivion": _OBLIVION,
    "Fallout3": _FO3,
    "FalloutNV": _FNV,
    "SkyrimLE": _SKYRIM_LE,
    "SkyrimSE": _SKYRIM_SE,
    "SkyrimAE": _SKYRIM_SE,
    "SkyrimVR": _SKYRIM_SE,
    "Fallout4": _FO4,
    "Fallout4VR": _FO4,
    "Fallout76": _FO76,
    "Starfield": _STARFIELD,
    "Morrowind": _MORROWIND,
}


def get_schema_for_game(game: str) -> GameSchema:
    """Return the schema for ``game``; raise ``KeyError`` if unknown."""

    return SCHEMAS_BY_GAME[game]


__all__ = [
    "SCHEMAS_BY_GAME",
    "FNVSchema",
    "FO3Schema",
    "FO4Schema",
    "FO76Schema",
    "MorrowindSchema",
    "OblivionSchema",
    "SkyrimLESchema",
    "SkyrimSESchema",
    "StarfieldSchema",
    "get_schema_for_game",
]
