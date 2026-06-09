"""Tests for evidence-driven glossary retrieval."""

# ruff: noqa: RUF001

from __future__ import annotations

from pathlib import Path

from conftest import PackFactory


def test_retriever_rejects_short_substring_noise(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader
    from bgs_translator.kb.retriever import GlossaryRetriever

    make_fixture_pack(
        "starfield-pack",
        [
            {"record_id": "noise-dot", "source": ".", "target": "。", "games": ["Starfield"]},
            {"record_id": "noise-u", "source": "U", "target": "U", "games": ["Starfield"]},
            {
                "record_id": "faction-uc",
                "source": "United Colonies",
                "target": "联合殖民地",
                "source_aliases": ["UC"],
                "games": ["Starfield"],
            },
            {
                "record_id": "place-new-atlantis",
                "source": "New Atlantis",
                "target": "新亚特兰蒂斯城",
                "games": ["Starfield"],
            },
            {"record_id": "watch", "source": "Watch", "target": "手表", "games": ["Starfield"]},
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        result = GlossaryRetriever(reader).collect_for_batch(
            ["United Colonies patrols New Atlantis."],
            "zh-cn",
            "Starfield",
        )
    finally:
        reader.close()

    included = {item.record_id: item for item in result.evidence if item.included}
    assert set(included) == {"faction-uc", "place-new-atlantis"}
    assert included["faction-uc"].matched_by == "source_exact"
    assert all(item.record_id not in {"noise-dot", "noise-u"} for item in result.evidence)
    assert all(item.record_id != "watch" for item in result.evidence)


def test_retriever_rag_does_not_recall_long_full_sentences(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader
    from bgs_translator.kb.retriever import GlossaryRetriever

    make_fixture_pack(
        "starfield-pack",
        [
            {
                "record_id": "long-sentence",
                "source": "Ensure the big show - the attack on New Atlantis - would be a success.",
                "target": "这是为了确保压轴大戏，也就是袭击新亚特兰蒂斯城，可以成功。",
                "games": ["Starfield"],
            },
            {
                "record_id": "short-concept",
                "source": "New Atlantis Terrormorph",
                "target": "新亚特兰蒂斯城骇变兽",
                "games": ["Starfield"],
            },
            {
                "record_id": "objective-sentence",
                "source": "Read the slate and identify the smuggler's ship",
                "target": "阅读写字板并找出走私者的飞船",
                "games": ["Starfield"],
            },
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        result = GlossaryRetriever(reader).collect_for_batch(
            ["Report a Terrormorph sighting near New Atlantis."],
            "zh-cn",
            "Starfield",
        )
    finally:
        reader.close()

    included = {item.record_id for item in result.evidence if item.included}
    assert included == {"short-concept"}


def test_player_and_dnt_rules_use_same_dedupe_and_evidence_pipeline(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader
    from bgs_translator.kb.retriever import GlossaryRetriever

    make_fixture_pack(
        "canonical",
        [
            {
                "record_id": "vanilla-starfield",
                "source": "Starfield",
                "target": "星空",
                "scope": "vanilla",
                "games": ["Starfield"],
            }
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
                "games": ["Starfield"],
            },
            {
                "record_id": "dnt-fc",
                "source": "FC",
                "target": "FC",
                "scope": "do_not_translate",
                "games": ["Starfield"],
            },
        ],
        is_user_pack=True,
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        result = GlossaryRetriever(reader).collect_for_batch(
            ["A new Starfield menu without FC in this line."],
            "zh-cn",
            "Starfield",
        )
    finally:
        reader.close()

    included = {item.record_id: item for item in result.evidence if item.included}
    excluded = {item.record_id: item for item in result.evidence if not item.included}
    assert included["player-starfield"].matched_by == "source_exact"
    assert included["dnt-fc"].matched_by == "source_exact"
    assert excluded["vanilla-starfield"].excluded_reason == "dedupe_source:player-starfield"


def test_budget_cap_keeps_evidence_for_omitted_terms(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader
    from bgs_translator.kb.retriever import GlossaryRetriever

    make_fixture_pack(
        "starfield-pack",
        [
            {"record_id": "term-a", "source": "Alpha Term", "target": "甲", "games": ["Starfield"]},
            {"record_id": "term-b", "source": "Beta Term", "target": "乙", "games": ["Starfield"]},
        ],
    )
    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        result = GlossaryRetriever(reader).collect_for_batch(
            ["Alpha Term and Beta Term"],
            "zh-cn",
            "Starfield",
            max_terms=1,
        )
    finally:
        reader.close()

    assert sum(1 for item in result.evidence if item.included) == 1
    assert any(item.excluded_reason == "budget_cap" for item in result.evidence)


def test_batch_plan_persists_glossary_evidence() -> None:
    from tests.test_batcher import plan, unit

    batch_plan = plan([unit("Travel to Whiterun")])

    assert batch_plan.batches[0].glossary_evidence
    assert batch_plan.batches[0].glossary_evidence[0].record_id == "place.whiterun"
