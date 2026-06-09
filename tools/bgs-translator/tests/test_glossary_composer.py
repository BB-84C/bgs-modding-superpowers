"""Tests for glossary subset collection and four-layer composition."""

from __future__ import annotations

from pathlib import Path

from conftest import PackFactory


def test_collect_for_batch_returns_matching_vanilla_and_dnt_entries(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.glossary import GlossaryComposer
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [
            {
                "record_id": "whiterun",
                "source": "Whiterun",
                "target": "白漫城",
                "category": "place",
            },
            {
                "record_id": "enaisiaion",
                "source": "EnaiSiaion",
                "target": "EnaiSiaion",
                "scope": "do_not_translate",
                "category": "brand",
            },
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        subset = GlossaryComposer(reader).collect_for_batch(
            ["The road to Whiterun", "EnaiSiaion"], "zh-cn", "SkyrimSE"
        )
    finally:
        reader.close()

    assert [entry.source for entry in subset.entries_by_scope["vanilla"]] == ["Whiterun"]
    assert [entry.source for entry in subset.entries_by_scope["do_not_translate"]] == ["EnaiSiaion"]


def test_collect_for_batch_includes_user_player_and_dnt_overrides_even_without_source_hit(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.glossary import GlossaryComposer
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [
            {"record_id": "uc", "source": "UC", "target": "联殖", "category": "faction"},
            {
                "record_id": "global-canon-dnt",
                "source": "UnrelatedGlobalCanonTerm",
                "target": "UnrelatedGlobalCanonTerm",
                "scope": "do_not_translate",
            },
        ],
    )
    make_fixture_pack(
        "translator-overrides-en-zhcn",
        [
            {
                "record_id": "player-starfield",
                "source": "Starfield",
                "target": "星空",
                "scope": "player",
                "confidence": "canonical",
            },
            {
                "record_id": "dnt-fc",
                "source": "FC",
                "target": "FC",
                "scope": "do_not_translate",
                "category": "brand",
            },
        ],
        is_user_pack=True,
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        subset = GlossaryComposer(reader).collect_for_batch(
            ["This source mentions only UC."], "zh-cn", "Starfield"
        )
    finally:
        reader.close()

    assert [entry.source for entry in subset.entries_by_scope["vanilla"]] == ["UC"]
    assert [entry.source for entry in subset.entries_by_scope["player"]] == ["Starfield"]
    assert [entry.source for entry in subset.entries_by_scope["do_not_translate"]] == ["FC"]


def test_collect_for_batch_caps_non_dnt_entries(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.glossary import GlossaryComposer
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [
            {
                "record_id": f"term-{index}",
                "source": f"Term{index}",
                "target": f"术语{index}",
            }
            for index in range(100)
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        subset = GlossaryComposer(reader).collect_for_batch(
            [" ".join(f"Term{index}" for index in range(100))], "zh-cn", "SkyrimSE", max_entries=20
        )
    finally:
        reader.close()

    assert subset.total_count() <= 20


def test_collect_for_batch_scores_high_occurrence_before_low_occurrence(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.glossary import GlossaryComposer
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [
            {"record_id": "high", "source": "Dragon", "target": "龙"},
            {"record_id": "low", "source": "Sword", "target": "剑"},
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        subset = GlossaryComposer(reader).collect_for_batch(
            ["Dragon Dragon Dragon Sword"], "zh-cn", "SkyrimSE", max_entries=2
        )
    finally:
        reader.close()

    assert [entry.source for entry in subset.entries_by_scope["vanilla"]] == ["Dragon", "Sword"]


def test_resolve_term_applies_scope_priority() -> None:
    from bgs_translator.kb.glossary import GlossaryComposer
    from bgs_translator.kb.models import GlossaryEntry

    vanilla = GlossaryEntry(
        record_id="vanilla",
        source="Requiem",
        source_aliases=[],
        source_lang="en",
        target="安魂曲",
        target_aliases=[],
        target_lang="zh-cn",
        scope="vanilla",
        scope_key=None,
        category="lore_term",
        confidence="canonical",
        notes=None,
        pack_id="canonical",
        games=[],
    )
    dnt = vanilla.model_copy(
        update={"record_id": "dnt", "target": "Requiem", "scope": "do_not_translate"}
    )
    mod = vanilla.model_copy(update={"record_id": "mod", "target": "安魂曲MOD", "scope": "mod"})
    player = vanilla.model_copy(update={"record_id": "player", "target": "玩家安魂曲", "scope": "player"})

    assert GlossaryComposer.resolve_term("Requiem", [vanilla, dnt]).action == "preserve_verbatim"
    resolved = GlossaryComposer.resolve_term("Requiem", [vanilla, mod, player])

    assert resolved.action == "translate_to"
    assert resolved.entry == player
    assert resolved.scope_used == "player"


def test_prompt_rendering_formats_confidence_hints(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.glossary import GlossaryComposer
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [
            {
                "record_id": "whiterun",
                "source": "Whiterun",
                "target": "白漫城",
                "category": "place",
                "confidence": "canonical",
            },
            {
                "record_id": "iron-sword",
                "source": "Iron Sword",
                "target": "铁剑",
                "category": "item",
                "confidence": "preferred",
            },
            {
                "record_id": "moonstone",
                "source": "Moonstone",
                "target": "月长石",
                "category": "item",
                "confidence": "candidate",
            },
            {
                "record_id": "enaisiaion",
                "source": "EnaiSiaion",
                "target": "EnaiSiaion",
                "scope": "do_not_translate",
                "category": "brand",
            },
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        composer = GlossaryComposer(reader)
        subset = composer.collect_for_batch(
            ["Whiterun Iron Sword Moonstone EnaiSiaion"], "zh-cn", "SkyrimSE"
        )
        glossary = composer.render_prompt_subset(subset, "glossary_subset_rendered")
        dnt = composer.render_prompt_subset(subset, "do_not_translate_list")
    finally:
        reader.close()

    assert "Whiterun → 白漫城 (place, canonical)" in glossary.splitlines()
    assert "Iron Sword → 铁剑 (item, preferred, prefer this exact form)" in glossary.splitlines()
    assert "Moonstone → 月长石 (item, candidate; LLM may use judgment)" in glossary.splitlines()
    assert dnt.splitlines() == ["EnaiSiaion"]
