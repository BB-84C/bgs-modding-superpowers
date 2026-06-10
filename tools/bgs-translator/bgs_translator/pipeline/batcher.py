"""Batch grouping and BatchPlan assembly ownership."""

# ruff: noqa: RUF001

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from bgs_translator.kb.glossary import GlossaryComposer, GlossarySubset
from bgs_translator.kb.models import GlossaryEntry, GlossaryMatchEvidence
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.mask import (
    MaskedUnit,
    apply_skip_heuristics,
    build_masked_unit,
    contains_prompt_protected_span,
    mask_prompt_protected_spans,
    strip_prompt_protected_spans,
)
from bgs_translator.pipeline.prompt import load_template, render_prompt

REGISTERS = Literal[
    "dialogue",
    "ui_label",
    "item_name",
    "item_desc",
    "book_prose",
    "system_message",
    "mcm_setting",
]
LengthTier = Literal["short", "medium", "long"]


@dataclass(frozen=True)
class Batch:
    """One prompt-sized batch of masked translation units."""

    batch_id: str
    items: list[MaskedUnit]
    parent_context_summary: str | None
    glossary_subset: list[GlossaryEntry]
    do_not_translate: list[str]
    glossary_evidence: list[GlossaryMatchEvidence] = field(default_factory=list)
    system_prompt: str | None = None


@dataclass(frozen=True)
class BatchPlan:
    """A complete batch planning result for one run."""

    plan_id: str
    project: str
    profile_name: str
    target_lang: str
    register: str
    batches: list[Batch]
    total_items: int
    est_input_tokens: int
    est_output_tokens: int
    est_cost_usd: float
    sample_system_prompt: str


def length_tier(source: str) -> LengthTier:
    """Classify source length by UTF-8 byte count."""

    byte_len = len(source.encode("utf-8"))
    if byte_len < 100:
        return "short"
    if byte_len <= 500:
        return "medium"
    return "long"


def batch_size_for(tier: str, override: int | None = None) -> int:
    """Return the default item cap for a length tier, unless overridden."""

    if override is not None:
        return override
    sizes = {"short": 40, "medium": 20, "long": 10}
    return sizes[tier]


def estimate_tokens(text: str) -> int:
    """Cheap token estimate based on UTF-8 byte length."""

    return max(1, int(len(text.encode("utf-8")) / 4)) if text else 0


def batch_group_key(
    masked_unit: MaskedUnit,
    register: str,
    target_lang: str,
    glossary_subset_hash: str,
) -> tuple[str, str, str, int | None, LengthTier, str]:
    """Return the stable grouping key for a masked unit."""

    parent_context = getattr(masked_unit.unit, "parent_context", None)
    parent_formid = None if parent_context is None else int(parent_context.parent_formid)
    return (
        target_lang,
        register,
        masked_unit.unit.signature,
        parent_formid,
        length_tier(masked_unit.unit.source),
        glossary_subset_hash,
    )


def plan_batches(
    units: list[TranslationUnit],
    *,
    project: str,
    profile_name: str,
    target_lang: str,
    register: str,
    glossary_composer: GlossaryComposer,
    game: str,
    mod_slug: str | None = None,
    batch_size: int | None = None,
    cost_estimator: Callable[[int, int], float] | None = None,
    game_lore_world: str | None = None,
    game_context_lore_summary: str | None = None,
    mod_context_name: str | None = None,
    mod_context_theme: str | None = None,
    style_directives: str | None = None,
    force_input_order_batches: bool = False,
    glossary_max_terms: int = 500,
    glossary_max_prompt_chars: int = 80000,
) -> BatchPlan:
    """Apply masks, group compatible units, pack batches, and estimate cost."""

    batches: list[Batch] = []
    masked_units = [masked_unit for masked_unit in (build_masked_unit(unit) for unit in units) if not masked_unit.skip_llm]
    if force_input_order_batches:
        cap = batch_size or 100
        batches.extend(
            _build_batches_from_chunks(
                masked_units,
                cap=cap,
                target_lang=target_lang,
                game=game,
                project=project,
                mod_slug=mod_slug,
                game_lore_world=game_lore_world,
                game_context_lore_summary=game_context_lore_summary,
                mod_context_name=mod_context_name,
                mod_context_theme=mod_context_theme,
                style_directives=style_directives,
                glossary_composer=glossary_composer,
                glossary_max_terms=glossary_max_terms,
                glossary_max_prompt_chars=glossary_max_prompt_chars,
            )
        )
    else:
        grouped: dict[tuple[str, str, str, int | None, LengthTier], list[MaskedUnit]] = defaultdict(list)
        for masked_unit in masked_units:
            grouped[_pre_glossary_batch_group_key(masked_unit, register, target_lang)].append(masked_unit)

        for key in sorted(grouped):
            items = grouped[key]
            tier = key[4]
            cap = batch_size_for(tier, batch_size)
            batches.extend(
                _build_batches_from_chunks(
                    items,
                    cap=cap,
                    target_lang=target_lang,
                    game=game,
                    project=project,
                    mod_slug=mod_slug,
                    game_lore_world=game_lore_world,
                    game_context_lore_summary=game_context_lore_summary,
                    mod_context_name=mod_context_name,
                    mod_context_theme=mod_context_theme,
                    style_directives=style_directives,
                    glossary_composer=glossary_composer,
                    glossary_max_terms=glossary_max_terms,
                    glossary_max_prompt_chars=glossary_max_prompt_chars,
                )
            )

    est_input = _estimate_input_tokens(batches)
    est_output = int(est_input * 1.3)
    est_cost = cost_estimator(est_input, est_output) if cost_estimator is not None else 0.0
    sample_prompt = (batches[0].system_prompt or "") if batches else ""
    return BatchPlan(
        plan_id=str(uuid.uuid4()),
        project=project,
        profile_name=profile_name,
        target_lang=target_lang,
        register=register,
        batches=batches,
        total_items=sum(len(batch.items) for batch in batches),
        est_input_tokens=est_input,
        est_output_tokens=est_output,
        est_cost_usd=est_cost,
        sample_system_prompt=sample_prompt,
    )


def _build_batches_from_chunks(
    items: list[MaskedUnit],
    *,
    cap: int,
    target_lang: str,
    game: str,
    project: str,
    mod_slug: str | None,
    game_lore_world: str | None,
    game_context_lore_summary: str | None,
    mod_context_name: str | None,
    mod_context_theme: str | None,
    style_directives: str | None,
    glossary_composer: GlossaryComposer,
    glossary_max_terms: int,
    glossary_max_prompt_chars: int,
) -> list[Batch]:
    return [
        _build_batch(
            items[start : start + cap],
            target_lang=target_lang,
            game=game,
            project=project,
            mod_slug=mod_slug,
            game_lore_world=game_lore_world,
            game_context_lore_summary=game_context_lore_summary,
            mod_context_name=mod_context_name,
            mod_context_theme=mod_context_theme,
            style_directives=style_directives,
            glossary_composer=glossary_composer,
            glossary_max_terms=glossary_max_terms,
            glossary_max_prompt_chars=glossary_max_prompt_chars,
        )
        for start in range(0, len(items), cap)
    ]


def _build_batch(
    chunk: list[MaskedUnit],
    *,
    target_lang: str,
    game: str,
    project: str,
    mod_slug: str | None,
    game_lore_world: str | None,
    game_context_lore_summary: str | None,
    mod_context_name: str | None,
    mod_context_theme: str | None,
    style_directives: str | None,
    glossary_composer: GlossaryComposer,
    glossary_max_terms: int,
    glossary_max_prompt_chars: int,
) -> Batch:
    result = glossary_composer.collect_for_batch_with_evidence(
        _glossary_query_sources(chunk),
        target_lang,
        game,
        mod_slug=mod_slug,
        max_terms=glossary_max_terms,
        max_prompt_chars=glossary_max_prompt_chars,
    )
    subset = GlossarySubset(entries_by_scope=result.entries_by_scope)
    flattened_subset = _flatten_subset(subset)
    do_not_translate = _do_not_translate_terms(subset, chunk)
    parent_context_summary = _parent_context_summary(chunk)
    return Batch(
        batch_id=str(uuid.uuid4()),
        items=chunk,
        parent_context_summary=parent_context_summary,
        glossary_subset=flattened_subset,
        do_not_translate=do_not_translate,
        glossary_evidence=result.evidence,
        system_prompt=_render_batch_prompt(
            game=game,
            project=project,
            game_lore_world=game_lore_world,
            game_context_lore_summary=game_context_lore_summary,
            mod_context_name=mod_context_name,
            mod_context_theme=mod_context_theme,
            style_directives=style_directives,
            glossary_composer=glossary_composer,
            glossary_subset=flattened_subset,
            do_not_translate=do_not_translate,
            parent_context_summary=parent_context_summary,
        ),
    )


def _pre_glossary_batch_group_key(
    masked_unit: MaskedUnit,
    register: str,
    target_lang: str,
) -> tuple[str, str, str, int | None, LengthTier]:
    parent_context = getattr(masked_unit.unit, "parent_context", None)
    parent_formid = None if parent_context is None else int(parent_context.parent_formid)
    return (
        target_lang,
        register,
        masked_unit.unit.signature,
        parent_formid,
        length_tier(masked_unit.unit.source),
    )


def _unique_sources(items: list[MaskedUnit]) -> list[str]:
    return list(dict.fromkeys(item.unit.source for item in items))


def _glossary_query_sources(items: list[MaskedUnit]) -> list[str]:
    sources = [strip_prompt_protected_spans(source) for source in _unique_sources(items)]
    return [source for source in dict.fromkeys(sources) if source]


def glossary_subset_hash(entries: list[GlossaryEntry]) -> str:
    """SHA-1 hash of sorted glossary record IDs."""

    digest = hashlib.sha1()
    for record_id in sorted(entry.record_id for entry in entries):
        digest.update(record_id.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _flatten_subset(subset: GlossarySubset) -> list[GlossaryEntry]:
    entries: list[GlossaryEntry] = []
    for scope in ("do_not_translate", "player", "mod", "vanilla"):
        entries.extend(subset.entries_by_scope.get(scope, []))
    return entries


def _do_not_translate_terms(subset: GlossarySubset, items: list[MaskedUnit]) -> list[str]:
    terms: list[str] = []
    for entry in subset.entries_by_scope.get("do_not_translate", []):
        if _entry_contains_protected_span(entry):
            continue
        terms.extend(form for form in entry.all_source_forms if not contains_prompt_protected_span(form))
    for item in items:
        reason = apply_skip_heuristics(item.unit.source)
        if reason is not None:
            terms.append(item.unit.source)
    return list(dict.fromkeys(terms))


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


def _parent_context_summary(items: list[MaskedUnit]) -> str | None:
    for item in items:
        parent_context = getattr(item.unit, "parent_context", None)
        if parent_context is not None:
            return str(getattr(parent_context, "summary", "")) or None
    return None


def _estimate_input_tokens(batches: list[Batch]) -> int:
    total = 0
    for batch in batches:
        total += estimate_tokens("\n".join(item.source_masked for item in batch.items))
        total += estimate_tokens("\n".join(entry.source for entry in batch.glossary_subset))
        total += estimate_tokens("\n".join(batch.do_not_translate))
    return total


def _render_batch_prompt(
    *,
    game: str,
    project: str,
    game_lore_world: str | None,
    game_context_lore_summary: str | None,
    mod_context_name: str | None,
    mod_context_theme: str | None,
    style_directives: str | None,
    glossary_composer: GlossaryComposer,
    glossary_subset: list[GlossaryEntry],
    do_not_translate: list[str],
    parent_context_summary: str | None,
) -> str:
    subset = GlossarySubset(
        entries_by_scope={
            "vanilla": [entry for entry in glossary_subset if entry.scope == "vanilla"],
            "mod": [entry for entry in glossary_subset if entry.scope == "mod"],
            "player": [entry for entry in glossary_subset if entry.scope == "player"],
            "do_not_translate": [
                entry for entry in glossary_subset if entry.scope == "do_not_translate"
            ],
        }
    )
    return render_prompt(
        load_template(),
        game_lore_world=_prompt_safe_text(game_lore_world or game),
        game_context_lore_summary=_prompt_safe_text(game_context_lore_summary or game),
        mod_context_name=_prompt_safe_text(mod_context_name or project),
        mod_context_theme=_prompt_safe_text(mod_context_theme or ""),
        style_directives=_prompt_safe_text(style_directives or "保持语义准确，保留占位符。"),
        glossary_subset_rendered=glossary_composer.render_prompt_subset(
            subset, "glossary_subset_rendered"
        ),
        do_not_translate_list="\n".join(_prompt_safe_text(term) for term in do_not_translate),
        parent_context_summary=_prompt_safe_text(parent_context_summary) if parent_context_summary else None,
    )


def _prompt_safe_text(text: str) -> str:
    return mask_prompt_protected_spans(text)[0]


__all__ = [
    "REGISTERS",
    "Batch",
    "BatchPlan",
    "batch_group_key",
    "batch_size_for",
    "estimate_tokens",
    "glossary_subset_hash",
    "length_tier",
    "plan_batches",
]
