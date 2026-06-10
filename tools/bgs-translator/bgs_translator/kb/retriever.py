"""Evidence-driven glossary retrieval for batch prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from bgs_translator.kb.models import GlossaryEntry, GlossaryMatchEvidence

SOURCE_CONTEXT_CHARS = 160
STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "identify",
    "just",
    "not",
    "read",
    "that",
    "the",
    "there",
    "this",
    "was",
    "were",
    "while",
    "with",
    "you",
    "your",
}
DEFAULT_PROMPT_GLOSSARY_MAX_TERMS = 500
DEFAULT_PROMPT_GLOSSARY_MAX_CHARS = 80000


@dataclass(frozen=True)
class GlossaryRetrievalResult:
    """Glossary retrieval output plus full explanation evidence."""

    entries_by_scope: dict[str, list[GlossaryEntry]]
    evidence: list[GlossaryMatchEvidence]

    def included_entries(self) -> list[GlossaryEntry]:
        """Return included entries in prompt priority order."""
        entries: list[GlossaryEntry] = []
        for scope in ("do_not_translate", "player", "mod", "vanilla"):
            entries.extend(self.entries_by_scope.get(scope, []))
        return entries


class GlossaryRetriever:
    """Collect glossary entries with deterministic evidence and prompt caps."""

    SCOPE_PRIORITY: ClassVar[dict[str, int]] = {
        "do_not_translate": 4,
        "player": 3,
        "mod": 2,
        "vanilla": 1,
    }
    MATCH_PRIORITY: ClassVar[dict[str, int]] = {
        "source_exact": 6,
        "alias_exact": 5,
        "normalized": 4,
        "dnt_rule": 3,
        "player_rule": 3,
        "rag": 1,
    }
    CONFIDENCE_WEIGHT: ClassVar[dict[str, float]] = {
        "canonical": 1.0,
        "preferred": 0.8,
        "candidate": 0.5,
    }

    def __init__(self, reader: object):
        self.reader = reader

    def collect_for_batch(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None = None,
        max_terms: int = DEFAULT_PROMPT_GLOSSARY_MAX_TERMS,
        max_prompt_chars: int = DEFAULT_PROMPT_GLOSSARY_MAX_CHARS,
    ) -> GlossaryRetrievalResult:
        """Collect candidate terms, dedupe them, and mark prompt inclusion."""
        entries = self._candidate_entries(source_strings, target_lang, game, mod_slug=mod_slug)
        entry_by_id = {entry.record_id: entry for entry in entries}
        source_tokens = set().union(*(_content_tokens(source) for source in source_strings))
        normalized_source_corpus = "\n".join(_normalize_form(source) for source in source_strings)
        evidence = [
            match
            for entry in entries
            for match in self._match_entry(
                entry,
                source_strings,
                source_tokens,
                normalized_source_corpus,
            )
        ]
        evidence = self._dedupe_evidence(evidence, entry_by_id)
        evidence = self._apply_budget(evidence, max_terms=max_terms, max_prompt_chars=max_prompt_chars)

        included_ids = {item.record_id for item in evidence if item.included}
        grouped = _empty_scope_map()
        for entry in entries:
            if entry.record_id in included_ids:
                grouped[entry.scope].append(entry)
        for scope_entries in grouped.values():
            scope_entries.sort(key=lambda entry: (entry.source.casefold(), entry.record_id))
        return GlossaryRetrievalResult(entries_by_scope=grouped, evidence=evidence)

    def _candidate_entries(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None,
    ) -> list[GlossaryEntry]:
        query_candidates = getattr(self.reader, "query_candidate_entries", None)
        if callable(query_candidates):
            try:
                return list(
                    query_candidates(
                        target_lang,
                        game,
                        mod_slug=mod_slug,
                        source_strings=source_strings,
                    )
                )
            except TypeError:
                return list(query_candidates(target_lang, game, mod_slug=mod_slug))

        query_matching = getattr(self.reader, "query_matching_entries", None)
        query_user = getattr(self.reader, "query_user_scope_entries", None)
        entries_by_id: dict[str, GlossaryEntry] = {}
        if callable(query_matching):
            for entry in query_matching(source_strings, target_lang, game, mod_slug=mod_slug):
                entries_by_id[entry.record_id] = entry
        if callable(query_user):
            for entry in query_user(target_lang, game, scopes={"player", "do_not_translate"}):
                entries_by_id[entry.record_id] = entry
        return list(entries_by_id.values())

    def _match_entry(
        self,
        entry: GlossaryEntry,
        source_strings: list[str],
        source_tokens: set[str],
        normalized_source_corpus: str,
    ) -> list[GlossaryMatchEvidence]:
        matches: list[GlossaryMatchEvidence] = []
        for index, form in enumerate(entry.all_source_forms):
            if not _is_matchable_form(form):
                continue
            exact = _find_boundary_match(form, source_strings)
            if exact is not None:
                matched_by = "source_exact" if index == 0 else "alias_exact"
                matches.append(self._evidence(entry, matched_by, form, exact, normalized_source_corpus))
                continue

            if _is_normalized_matchable(form):
                normalized_match = _find_normalized_match(form, source_strings)
                if normalized_match is not None:
                    matches.append(
                        self._evidence(entry, "normalized", form, normalized_match, normalized_source_corpus)
                    )
                    continue

        if matches:
            return [max(matches, key=self._evidence_rank_key)]

        if entry.scope == "do_not_translate":
            return [
                self._evidence(
                    entry,
                    "dnt_rule",
                    entry.source,
                    entry.source,
                    normalized_source_corpus,
                )
            ]
        if entry.scope == "player":
            return [
                self._evidence(
                    entry,
                    "player_rule",
                    entry.source,
                    entry.source,
                    normalized_source_corpus,
                )
            ]

        rag_match = _related_match(entry, source_tokens)
        if rag_match is not None:
            return [self._evidence(entry, "rag", rag_match, rag_match, normalized_source_corpus)]
        return []

    def _evidence(
        self,
        entry: GlossaryEntry,
        matched_by: str,
        matched_text: str,
        source_excerpt: str,
        normalized_source_corpus: str,
    ) -> GlossaryMatchEvidence:
        score = (
            self.MATCH_PRIORITY[matched_by]
            + self.SCOPE_PRIORITY[entry.scope] * 0.1
            + self.CONFIDENCE_WEIGHT[entry.confidence] * 0.01
            + min(_occurrence_count(matched_text, normalized_source_corpus), 10) * 0.001
        )
        return GlossaryMatchEvidence(
            term=entry.source,
            scope=entry.scope,
            record_id=entry.record_id,
            source=entry.source,
            target=entry.target,
            matched_by=matched_by,  # type: ignore[arg-type]
            matched_text=matched_text,
            source_excerpt=_excerpt(source_excerpt),
            score=round(score, 4),
            included=True,
            excluded_reason=None,
            dedupe_key=_dedupe_key(entry),
        )

    def _dedupe_evidence(
        self,
        evidence: list[GlossaryMatchEvidence],
        entry_by_id: dict[str, GlossaryEntry],
    ) -> list[GlossaryMatchEvidence]:
        kept_by_record: dict[str, GlossaryMatchEvidence] = {}
        output: list[GlossaryMatchEvidence] = []
        for item in sorted(evidence, key=self._evidence_rank_key, reverse=True):
            existing = kept_by_record.get(item.record_id)
            if existing is None:
                kept_by_record[item.record_id] = item
            else:
                output.append(
                    item.model_copy(
                        update={
                            "included": False,
                            "excluded_reason": f"dedupe_record:{existing.record_id}",
                        }
                    )
                )

        kept_by_source: dict[str, GlossaryMatchEvidence] = {}
        for item in sorted(kept_by_record.values(), key=self._evidence_rank_key, reverse=True):
            key = item.dedupe_key
            existing = kept_by_source.get(key)
            if existing is None:
                kept_by_source[key] = item
                continue
            kept_entry = entry_by_id.get(existing.record_id)
            candidate_entry = entry_by_id.get(item.record_id)
            if candidate_entry is not None and kept_entry is not None and self._beats(item, existing):
                kept_by_source[key] = item
                output.append(
                    existing.model_copy(
                        update={
                            "included": False,
                            "excluded_reason": f"dedupe_source:{item.record_id}",
                        }
                    )
                )
            else:
                output.append(
                    item.model_copy(
                        update={
                            "included": False,
                            "excluded_reason": f"dedupe_source:{existing.record_id}",
                        }
                    )
                )

        output.extend(kept_by_source.values())
        return sorted(output, key=self._evidence_rank_key, reverse=True)

    def _apply_budget(
        self,
        evidence: list[GlossaryMatchEvidence],
        *,
        max_terms: int,
        max_prompt_chars: int,
    ) -> list[GlossaryMatchEvidence]:
        included_count = 0
        char_count = 0
        output: list[GlossaryMatchEvidence] = []
        for item in evidence:
            if not item.included:
                output.append(item)
                continue
            line_chars = len(f"{item.source} -> {item.target}")
            if included_count >= max_terms or char_count + line_chars > max_prompt_chars:
                output.append(
                    item.model_copy(
                        update={
                            "included": False,
                            "excluded_reason": "budget_cap",
                        }
                    )
                )
                continue
            included_count += 1
            char_count += line_chars
            output.append(item)
        return output

    def _evidence_rank_key(self, item: GlossaryMatchEvidence) -> tuple[int, int, float, str]:
        return (
            self.SCOPE_PRIORITY[item.scope],
            self.MATCH_PRIORITY[item.matched_by],
            item.score,
            item.record_id,
        )

    def _beats(self, candidate: GlossaryMatchEvidence, existing: GlossaryMatchEvidence) -> bool:
        return self._evidence_rank_key(candidate) > self._evidence_rank_key(existing)


def _empty_scope_map() -> dict[str, list[GlossaryEntry]]:
    return {"vanilla": [], "mod": [], "player": [], "do_not_translate": []}


def _is_matchable_form(form: str) -> bool:
    normalized = _normalize_form(form)
    if len(normalized) < 2:
        return False
    if not any(char.isalnum() for char in form):
        return False
    return True


def _is_normalized_matchable(form: str) -> bool:
    if len(_normalize_form(form)) < 4:
        return False
    return any(not char.isalnum() for char in form)


def _find_boundary_match(form: str, source_strings: list[str]) -> str | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(form)}(?![A-Za-z0-9])", re.IGNORECASE)
    for source in source_strings:
        match = pattern.search(source)
        if match is not None:
            return source
    return None


def _find_normalized_match(form: str, source_strings: list[str]) -> str | None:
    needle = _normalize_form(form)
    if len(needle) < 4:
        return None
    for source in source_strings:
        if needle in _normalize_form(source):
            return source
    return None


def _related_match(entry: GlossaryEntry, source_tokens: set[str]) -> str | None:
    if len(entry.source) > 80 or _looks_like_sentence(entry.source):
        return None
    if _raw_tokens(entry.source) & STOP_WORDS:
        return None
    term_tokens = _content_tokens(entry.source)
    if len(term_tokens) < 2 or len(term_tokens) > 6:
        return None
    required_overlap = min(2, len(term_tokens))
    if len(set(term_tokens) & source_tokens) >= required_overlap:
        return " ".join(sorted(set(term_tokens) & source_tokens))
    return None


def _content_tokens(text: str) -> set[str]:
    return {token for token in _raw_tokens(text) if len(token) >= 3 and token not in STOP_WORDS}


def _raw_tokens(text: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", text)}


def _looks_like_sentence(text: str) -> bool:
    return any(marker in text for marker in (".", "?", "!", ",", ";", ":"))


def _normalize_form(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


def _dedupe_key(entry: GlossaryEntry) -> str:
    normalized = _normalize_form(entry.source)
    return normalized or entry.record_id


def _occurrence_count(form: str, normalized_source_corpus: str) -> int:
    normalized = _normalize_form(form)
    if not normalized:
        return 0
    return normalized_source_corpus.count(normalized)


def _excerpt(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= SOURCE_CONTEXT_CHARS:
        return compact
    return compact[: SOURCE_CONTEXT_CHARS - 1].rstrip() + "..."


__all__ = ["GlossaryRetrievalResult", "GlossaryRetriever"]
