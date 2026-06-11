"""Pydantic models for bgs-kb glossary records."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GlossaryEntry(BaseModel):
    """A glossary-entry record read from a bgs-kb pack SQLite store."""

    record_id: str
    source: str
    source_aliases: list[str]
    source_lang: str
    target: str
    target_aliases: list[str]
    target_lang: str
    scope: Literal["vanilla", "mod", "player", "do_not_translate"]
    scope_key: str | None
    category: str | None
    confidence: Literal["canonical", "preferred", "candidate"]
    notes: str | None
    pack_id: str
    games: list[str]

    @property
    def all_source_forms(self) -> list[str]:
        """Source + aliases, deduplicated in first-seen order."""
        return list(dict.fromkeys([self.source, *self.source_aliases]))


class ResolvedTerm(BaseModel):
    """Result of resolving a single term against all four glossary layers."""

    term: str
    action: Literal["preserve_verbatim", "translate_to", "no_constraint"]
    entry: GlossaryEntry | None
    scope_used: str | None


class GlossaryMatchEvidence(BaseModel):
    """Why one glossary entry was considered for a batch prompt."""

    term: str
    scope: Literal["vanilla", "mod", "player", "do_not_translate"]
    record_id: str
    source: str
    target: str
    matched_by: Literal[
        "source_exact",
        "alias_exact",
        "normalized",
        "rag",
        "player_rule",
        "dnt_rule",
    ]
    matched_text: str
    source_excerpt: str
    score: float
    included: bool
    excluded_reason: str | None
    dedupe_key: str


__all__ = ["GlossaryEntry", "GlossaryMatchEvidence", "ResolvedTerm"]
