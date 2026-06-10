"""Four-layer glossary composition ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from bgs_translator.kb.models import GlossaryEntry, ResolvedTerm
from bgs_translator.kb.reader import KBGlossaryReader
from bgs_translator.kb.retriever import GlossaryRetrievalResult, GlossaryRetriever
from bgs_translator.pipeline.mask import (
    contains_prompt_protected_span,
    mask_prompt_protected_spans,
)

DEFAULT_PROMPT_GLOSSARY_MAX_TERMS = 500
DEFAULT_PROMPT_GLOSSARY_MAX_CHARS = 80000


@dataclass
class GlossarySubset:
    """A bundle of glossary entries relevant to a batch of source strings."""

    entries_by_scope: dict[str, list[GlossaryEntry]]

    def total_count(self) -> int:
        """Return the total number of entries in all scope buckets."""
        return sum(len(entries) for entries in self.entries_by_scope.values())


class GlossaryComposer:
    """Four-layer composing resolution per PRD §1."""

    SCOPE_PRIORITY: ClassVar[dict[str, int]] = {
        "do_not_translate": 4,
        "player": 3,
        "mod": 2,
        "vanilla": 1,
    }

    CONFIDENCE_WEIGHT: ClassVar[dict[str, float]] = {
        "canonical": 1.0,
        "preferred": 0.8,
        "candidate": 0.5,
    }

    def __init__(self, reader: KBGlossaryReader):
        self.reader = reader
        self.retriever = GlossaryRetriever(reader)

    def collect_for_batch(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        mod_slug: str | None = None,
        max_entries: int = DEFAULT_PROMPT_GLOSSARY_MAX_TERMS,
    ) -> GlossarySubset:
        """Collect, score, cap, and bucket glossary entries for a batch."""
        result = self.collect_for_batch_with_evidence(
            source_strings,
            target_lang,
            game,
            mod_slug=mod_slug,
            max_terms=max_entries,
        )
        return GlossarySubset(entries_by_scope=result.entries_by_scope)

    def collect_for_batch_with_evidence(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        mod_slug: str | None = None,
        max_terms: int = DEFAULT_PROMPT_GLOSSARY_MAX_TERMS,
        max_prompt_chars: int = DEFAULT_PROMPT_GLOSSARY_MAX_CHARS,
    ) -> GlossaryRetrievalResult:
        """Collect glossary entries and retain full match evidence."""
        return self.retriever.collect_for_batch(
            source_strings,
            target_lang,
            game,
            mod_slug=mod_slug,
            max_terms=max_terms,
            max_prompt_chars=max_prompt_chars,
        )

    @staticmethod
    def resolve_term(term: str, entries: list[GlossaryEntry]) -> ResolvedTerm:
        """Resolve a single term using DNT > player > mod > vanilla priority."""
        for scope in ("do_not_translate", "player", "mod", "vanilla"):
            for entry in entries:
                if entry.scope == scope and _entry_matches_term(entry, term):
                    if scope == "do_not_translate":
                        return ResolvedTerm(
                            term=term,
                            action="preserve_verbatim",
                            entry=entry,
                            scope_used=scope,
                        )
                    return ResolvedTerm(
                        term=term,
                        action="translate_to",
                        entry=entry,
                        scope_used=scope,
                    )
        return ResolvedTerm(term=term, action="no_constraint", entry=None, scope_used=None)

    def render_prompt_subset(
        self,
        subset: GlossarySubset,
        slot: Literal["glossary_subset_rendered", "do_not_translate_list"],
    ) -> str:
        """Format glossary entries for the named prompt-template slot."""
        if slot == "do_not_translate_list":
            return "\n".join(_dedupe_source_forms(subset.entries_by_scope["do_not_translate"]))

        lines: list[str] = []
        for scope in ("player", "mod", "vanilla"):
            lines.extend(
                line
                for entry in subset.entries_by_scope[scope]
                if (line := _render_glossary_line(entry)) is not None
            )
        return "\n".join(lines)

    def _score_entry(self, entry: GlossaryEntry, source_strings: list[str]) -> float:
        occurrence_count = _occurrence_count(entry, source_strings)
        return (
            occurrence_count
            * float(self.SCOPE_PRIORITY[entry.scope])
            * self.CONFIDENCE_WEIGHT[entry.confidence]
        )


def _empty_scope_map() -> dict[str, list[GlossaryEntry]]:
    return {"vanilla": [], "mod": [], "player": [], "do_not_translate": []}


def _occurrence_count(entry: GlossaryEntry, source_strings: list[str]) -> int:
    count = 0
    haystacks = [source_string.casefold() for source_string in source_strings]
    for form in entry.all_source_forms:
        needle = form.casefold()
        if not needle:
            continue
        count += sum(haystack.count(needle) for haystack in haystacks)
    return count


def _entry_matches_term(entry: GlossaryEntry, term: str) -> bool:
    term_folded = term.casefold()
    return any(form.casefold() == term_folded for form in entry.all_source_forms)


def _render_glossary_line(entry: GlossaryEntry) -> str | None:
    if _entry_contains_protected_span(entry):
        return None
    category = entry.category or "uncategorized"
    if entry.confidence == "preferred":
        confidence = "preferred, prefer this exact form"
    elif entry.confidence == "candidate":
        confidence = "candidate; LLM may use judgment"
    else:
        confidence = "canonical"
    protected_map: dict[str, str] = {}
    source, protected_map = mask_prompt_protected_spans(entry.source, protected_map)
    target, _protected_map = mask_prompt_protected_spans(entry.target, protected_map)
    return f"{source} → {target} ({category}, {confidence})"


def _dedupe_source_forms(entries: list[GlossaryEntry]) -> list[str]:
    forms: list[str] = []
    for entry in entries:
        if _entry_contains_protected_span(entry):
            continue
        forms.extend(entry.all_source_forms)
    return list(dict.fromkeys(mask_prompt_protected_spans(form)[0] for form in forms))


def _entry_contains_protected_span(entry: GlossaryEntry) -> bool:
    return any(
        contains_prompt_protected_span(text)
        for text in [
            entry.source,
            entry.target,
            *entry.source_aliases,
            *entry.target_aliases,
        ]
    )


__all__ = ["GlossaryComposer", "GlossarySubset"]
