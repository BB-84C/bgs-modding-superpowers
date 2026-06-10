"""Record-signature filters for vanilla terminology retrieval.

The official localization SST packs are useful as a terminology source, but
they are not a terminology database. Large packs contain full dialogue lines,
book prose, loading-screen text, settings, and many technical labels. Batch
prompt RAG should prefer record types that usually carry names, places,
factions, items, spells, quests, perks, UI concepts, and other reusable
player-facing concepts.
"""

from __future__ import annotations

import re

TERM_SEED_SIGNATURES: frozenset[str] = frozenset(
    {
        # Characters, factions, locations, worlds.
        "NPC_",
        "FACT",
        "RACE",
        "CLAS",
        "LCTN",
        "CELL",
        "WRLD",
        "REGN",
        "BIOM",
        # Quests and player-facing activity concepts.
        "DIAL",
        "CHAL",
        # Items, equipment, object names, crafting concepts.
        "WEAP",
        "ARMO",
        "AMMO",
        "ALCH",
        "MISC",
        "KEYM",
        "BOOK",
        "CONT",
        "ACTI",
        "DOOR",
        "FLOR",
        "FURN",
        "MSTT",
        "STAT",
        "TERM",
        "COBJ",
        "OMOD",
        "RSPJ",
        "GBFM",
        "INNR",
        # Abilities, effects, skills, keywords, messages that name UI concepts.
        "AVIF",
        "PERK",
        "SPEL",
        "MGEF",
        "ENCH",
        "KYWD",
        # Starfield/newer gameplay concept records seen in official l10n packs.
        "TMLM",
        "IRES",
        "HDPT",
        "PMFT",
        "DMGT",
    }
)

TERM_SEED_FIELDS: frozenset[tuple[str, str]] = frozenset(
    {
        ("ACTI", "FULL"),
        ("ALCH", "FULL"),
        ("AMMO", "FULL"),
        ("ARMO", "FULL"),
        ("AVIF", "FULL"),
        ("BOOK", "FULL"),
        ("CELL", "FULL"),
        ("CLAS", "FULL"),
        ("CONT", "FULL"),
        ("DIAL", "FULL"),
        ("DMGT", "FULL"),
        ("DOOR", "FULL"),
        ("FACT", "FULL"),
        ("FLOR", "FULL"),
        ("FURN", "FULL"),
        ("GBFM", "FULL"),
        ("IRES", "FULL"),
        ("INNR", "WNAM"),
        ("KEYM", "FULL"),
        ("KYWD", "FULL"),
        ("LCTN", "FULL"),
        ("MGEF", "FULL"),
        ("MISC", "FULL"),
        ("NPC_", "FULL"),
        ("OMOD", "FULL"),
        ("PERK", "FULL"),
        ("RACE", "FULL"),
        ("RSPJ", "FULL"),
        ("SPEL", "FULL"),
        ("STAT", "FULL"),
        ("TERM", "FULL"),
        ("TMLM", "ITXT"),
        ("WEAP", "FULL"),
        ("WRLD", "FULL"),
        ("MESG", "ITXT"),
        ("MESG", "FULL"),
        ("QUST", "FULL"),
        ("QUST", "NNAM"),
        ("QUST", "QMDT"),
        ("QUST", "QMDP"),
    }
)

CONTEXT_ONLY_FIELDS: frozenset[tuple[str, str]] = frozenset(
    {
        ("BOOK", "DESC"),
        ("LSCR", "DESC"),
        ("QUST", "CNAM"),
        ("QUST", "QMSU"),
        ("INFO", "NAM1"),
        ("TERM", "BTXT"),
        ("TERM", "RNAM"),
        ("TMLM", "BTXT"),
    }
)

TERMINOLOGY_SOURCE_EXCLUDED_SIGNATURES: frozenset[str] = frozenset(
    {
        # Full dialogue is too broad for terminology RAG and dominates official
        # localization packs.
        "INFO",
        # Mostly placed references, scene/control flow, visuals, audio, navmesh,
        # packages, weather/lighting, leveled structure, and engine data.
        "REFR",
        "ACHR",
        "ACRE",
        "SCEN",
        "PACK",
        "AISE",
        "NAVM",
        "NAVI",
        "WTHR",
        "CLMT",
        "LGTM",
        "IMGS",
        "IMAD",
        "MUSC",
        "MUST",
        "SNDR",
        "SOUN",
        "TXST",
        "MATO",
        "LTEX",
        "LAND",
        "TREE",
        "IDLE",
        "PROJ",
        "EXPL",
        "HAZD",
        "FLST",
        "GMST",
        "HULL",
        "LVLI",
        "LVLN",
        "LVLC",
        "PKIN",
        "PNDT",
        "STDT",
        "TES4",
    }
)

# Backwards-compatible public names used by tests and debugging snippets.
TERMINOLOGY_SOURCE_SIGNATURES = TERM_SEED_SIGNATURES
TERMINOLOGY_SOURCE_FIELDS = TERM_SEED_FIELDS

_RECORD_RE = re.compile(r"(?:^|[\s;`])record\s*=\s*([A-Za-z0-9_]{4}):([A-Za-z0-9_]{4})", re.I)
_BODY_RECORD_RE = re.compile(r"-\s*Record:\s*`([A-Za-z0-9_]{4}):([A-Za-z0-9_]{4})`", re.I)
_PROTECTED_SPAN_RE = re.compile(r"<(?:Alias|Global|Token|Variable|Ref|Base|Form|Value)=[^>]+>", re.I)
_MASK_TOKEN_RE = re.compile(r"\{P\d+\}|\{\{P\d+\}\}")


def extract_record_signature_field(*, body_md: str | None, notes: str | None) -> tuple[str, str] | None:
    """Return ``(SIGNATURE, FIELD)`` from current SST-derived glossary metadata."""

    for value, pattern in ((body_md or "", _BODY_RECORD_RE), (notes or "", _RECORD_RE)):
        match = pattern.search(value)
        if match is not None:
            return match.group(1).upper(), match.group(2).upper()
    return None


def is_terminology_source_record(signature: str, field: str | None = None) -> bool:
    """Return whether a vanilla localization row is useful for term RAG."""

    sig = str(signature or "").strip().upper()
    fld = str(field or "").strip().upper()
    if not sig:
        return True
    if (sig, fld) in CONTEXT_ONLY_FIELDS:
        return False
    if sig in TERMINOLOGY_SOURCE_EXCLUDED_SIGNATURES and (sig, fld) not in TERM_SEED_FIELDS:
        return False
    return (sig, fld) in TERM_SEED_FIELDS or (sig in TERM_SEED_SIGNATURES and fld == "FULL")


def is_terminology_term_text(text: str) -> bool:
    """Return whether a source string is safe and useful as a glossary term."""

    value = " ".join(str(text or "").split())
    if len(value) < 2:
        return False
    if _PROTECTED_SPAN_RE.search(value) or _MASK_TOKEN_RE.search(value):
        return False
    if "_" in value:
        return False
    if not any(char.isalpha() for char in value):
        return False
    if re.fullmatch(r"[\d\s.,:+\\/%$#-]+", value):
        return False
    if "\\" in value or ("/" in value and not re.search(r"\s/\s", value)):
        return False
    return True


__all__ = [
    "CONTEXT_ONLY_FIELDS",
    "TERMINOLOGY_SOURCE_EXCLUDED_SIGNATURES",
    "TERMINOLOGY_SOURCE_FIELDS",
    "TERMINOLOGY_SOURCE_SIGNATURES",
    "TERM_SEED_FIELDS",
    "TERM_SEED_SIGNATURES",
    "extract_record_signature_field",
    "is_terminology_source_record",
    "is_terminology_term_text",
]
