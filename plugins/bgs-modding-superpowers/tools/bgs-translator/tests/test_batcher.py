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
        if any("Deliver" in source for source in source_strings):
            entries.append(
                entry(
                    "quest.deliver.alias",
                    "Deliver <Alias=PrimaryRef> to <Alias=TargetLocation>",
                    "将<Alias=PrimaryRef>送至<Alias=TargetLocation>",
                    "lore_term",
                )
            )
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


def test_forced_input_order_batches_honor_custom_batch_size() -> None:
    batch_plan = plan(
        [unit(f"Quest objective {i}", "QUST", "FULL") for i in range(500)],
        batch_size=100,
        force_input_order_batches=True,
    )
    assert [len(batch.items) for batch in batch_plan.batches] == [100, 100, 100, 100, 100]

    one_per_batch = plan(
        [unit(f"Quest objective {i}", "QUST", "FULL") for i in range(500)],
        batch_size=1,
        force_input_order_batches=True,
    )
    assert len(one_per_batch.batches) == 500
    assert all(len(batch.items) == 1 for batch in one_per_batch.batches)


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


def test_batch_level_glossary_combines_terms_for_same_chunk() -> None:
    batch_plan = plan([unit("Travel to Whiterun"), unit("Requires SKSE")])
    assert len(batch_plan.batches) == 1
    assert {entry.record_id for entry in batch_plan.batches[0].glossary_subset} == {
        "place.whiterun",
        "brand.skse",
    }


def test_each_chunk_has_its_own_system_prompt_glossary() -> None:
    batch_plan = plan([unit("Travel to Whiterun"), unit("Requires SKSE")], batch_size=1)
    prompts = [batch.system_prompt or "" for batch in batch_plan.batches]

    assert len(prompts) == 2
    assert "Whiterun → 白漫城" in prompts[0]
    assert "\nSKSE\n" not in prompts[0]
    assert "Whiterun → 白漫城" not in prompts[1]
    assert "\nSKSE\n" in prompts[1]


def test_token_estimates_and_sample_prompt_are_populated() -> None:
    batch_plan = plan([unit("Travel to Whiterun")])
    assert batch_plan.est_input_tokens > 0
    assert batch_plan.est_output_tokens > 0
    assert batch_plan.sample_system_prompt.strip()


def test_system_prompt_masks_protected_spans_in_context_and_glossary() -> None:
    batch_plan = plan(
        [unit("Deliver <Alias=PrimaryRef> to <Alias=TargetLocation>", "QUST", "NNAM")],
        game_context_lore_summary="Keep <Alias=TargetLocation> protected.",
        mod_context_theme="Uses <Alias=PrimaryRef> and <Global=MissionBoardPassenger01Amount> dynamically.",
        style_directives="Never expose <Alias=TargetLocation> or <Global=MissionBoardPassenger01Amount> in prompts.",
    )
    prompt = batch_plan.batches[0].system_prompt or ""

    assert "<Alias=" not in prompt
    assert "<Global=" not in prompt
    assert "Deliver {{P0}} to {{P1}} → 将{{P0}}送至{{P1}}" not in prompt
    assert "Deliver  to" not in prompt
    assert "Never expose {{P0}} or {{P1}} in prompts." in prompt
