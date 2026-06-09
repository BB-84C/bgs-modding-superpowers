"""Tests for batch planning and grouping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bgs_translator.kb.glossary import GlossaryComposer
from bgs_translator.kb.models import GlossaryEntry
from bgs_translator.parsers.tes4_family import TranslationUnit


@dataclass(frozen=True)
class ParentContext:
    parent_formid: int
    summary: str


class FakeReader:
    def query_matching_entries(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        mod_slug: str | None = None,
    ) -> list[GlossaryEntry]:
        del target_lang, game, mod_slug
        entries: list[GlossaryEntry] = []
        if any("Whiterun" in source for source in source_strings):
            entries.append(entry("place.whiterun", "Whiterun", "白漫城", "place"))
        if any("SKSE" in source for source in source_strings):
            entries.append(entry("brand.skse", "SKSE", "SKSE", "brand", scope="do_not_translate"))
        return entries

    def query_user_scope_entries(
        self,
        target_lang: str,
        game: str,
        *,
        scopes: set[str],
    ) -> list[GlossaryEntry]:
        del target_lang, game, scopes
        return []


def unit(source: str, sig: str = "WEAP", field: str = "FULL") -> TranslationUnit:
    return TranslationUnit("Test.esp", 1, 1, "EDID", sig, field, source=source)


def with_parent(base: TranslationUnit, parent_formid: int) -> TranslationUnit:
    object.__setattr__(base, "parent_context", ParentContext(parent_formid, "Quest dialogue"))
    return base


def composer() -> GlossaryComposer:
    return GlossaryComposer(FakeReader())  # type: ignore[arg-type]


def entry(
    record_id: str,
    source: str,
    target: str,
    category: str,
    *,
    scope: str = "vanilla",
) -> GlossaryEntry:
    return GlossaryEntry(
        record_id=record_id,
        source=source,
        source_aliases=[],
        source_lang="en",
        target=target,
        target_aliases=[],
        target_lang="zh-cn",
        scope=scope,  # type: ignore[arg-type]
        scope_key=None,
        category=category,
        confidence="canonical",
        notes=None,
        pack_id="test-pack",
        games=["SkyrimSE"],
    )


def plan(sources: list[TranslationUnit], **kwargs: Any):  # type: ignore[no-untyped-def]
    from bgs_translator.pipeline.batcher import plan_batches

    return plan_batches(
        sources,
        project="demo",
        profile_name="fake",
        target_lang="zh-cn",
        register="dialogue",
        glossary_composer=composer(),
        game="SkyrimSE",
        **kwargs,
    )


def test_group_by_signature_keeps_weapon_and_armor_separate() -> None:
    batch_plan = plan([unit("Iron Sword", "WEAP"), unit("Iron Armor", "ARMO")])
    signatures_by_batch = [{item.unit.signature for item in batch.items} for batch in batch_plan.batches]
    assert {frozenset(signatures) for signatures in signatures_by_batch} == {
        frozenset({"WEAP"}),
        frozenset({"ARMO"}),
    }


def test_length_tier_and_default_batch_sizes() -> None:
    from bgs_translator.pipeline.batcher import batch_size_for, length_tier

    assert length_tier("a" * 50) == "short"
    assert length_tier("a" * 200) == "medium"
    assert length_tier("a" * 700) == "long"
    assert batch_size_for("short") == 40
    assert batch_size_for("medium") == 20
    assert batch_size_for("long") == 10
    assert batch_size_for("long", override=3) == 3


def test_batch_size_defaults_are_enforced() -> None:
    batch_plan = plan([unit(f"Long sentence {i}") for i in range(41)])
    assert sorted(len(batch.items) for batch in batch_plan.batches) == [1, 40]


def test_parent_context_groups_info_in_same_dialogue() -> None:
    batch_plan = plan(
        [
            with_parent(unit("Line A", "INFO", "NAM1"), 0x123),
            with_parent(unit("Line B", "INFO", "NAM1"), 0x123),
            with_parent(unit("Line C", "INFO", "NAM1"), 0x456),
        ]
    )
    grouped_parent_ids = [
        {item.unit.parent_context.parent_formid for item in batch.items}
        for batch in batch_plan.batches
    ]
    assert {frozenset(ids) for ids in grouped_parent_ids} == {frozenset({0x123}), frozenset({0x456})}


def test_glossary_hash_differs_between_different_subsets() -> None:
    batch_plan = plan([unit("Travel to Whiterun"), unit("Requires SKSE")])
    subset_ids = [
        {entry.record_id for entry in batch.glossary_subset}
        for batch in batch_plan.batches
    ]
    assert {frozenset(ids) for ids in subset_ids} == {
        frozenset({"place.whiterun"}),
        frozenset({"brand.skse"}),
    }


def test_token_estimates_and_sample_prompt_are_populated() -> None:
    batch_plan = plan([unit("Travel to Whiterun")])
    assert batch_plan.est_input_tokens > 0
    assert batch_plan.est_output_tokens > 0
    assert batch_plan.sample_system_prompt.strip()
