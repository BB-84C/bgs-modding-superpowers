"""Tests for system prompt template rendering."""

from __future__ import annotations


def test_default_template_has_all_required_slots() -> None:
    from bgs_translator.pipeline.prompt import DEFAULT_TEMPLATE, validate_template

    ok, problems = validate_template(DEFAULT_TEMPLATE)
    assert ok is True
    assert problems == []


def test_validate_template_detects_missing_required_slot() -> None:
    from bgs_translator.pipeline.prompt import validate_template

    ok, problems = validate_template("Only ${game_lore_world}")
    assert ok is False
    assert any("missing required slot" in problem for problem in problems)


def test_render_prompt_replaces_all_slots() -> None:
    from bgs_translator.pipeline.prompt import load_template, render_prompt
    prompt = render_prompt(
        load_template(),
        game_lore_world="Skyrim",
        game_context_lore_summary="Tamriel politics",
        mod_context_name="Demo Mod",
        mod_context_theme="Quest mod",
        style_directives="Concise",
        record_signature_context="- WEAP: Meaning this entry is from a Weapon record.",
        glossary_subset_rendered="- Whiterun → 白漫城 (place, canonical)",
        do_not_translate_list="- SKSE",
        parent_context_summary="This is dialogue.",
        ad_hoc_context="Extra notes.",
    )
    assert "${" not in prompt
    assert "Demo Mod" in prompt


def test_optional_slot_label_lines_are_omitted_when_empty() -> None:
    from bgs_translator.pipeline.prompt import load_template, render_prompt
    prompt = render_prompt(
        load_template(),
        game_lore_world="Skyrim",
        game_context_lore_summary="Tamriel politics",
        mod_context_name="Demo Mod",
        mod_context_theme="Quest mod",
        style_directives="Concise",
        record_signature_context="",
        glossary_subset_rendered="",
        do_not_translate_list="",
        parent_context_summary=None,
        ad_hoc_context=None,
    )
    assert "补充上下文" not in prompt
    assert "parent_context_summary_if_present" not in prompt


def test_placeholder_literal_is_preserved() -> None:
    from bgs_translator.pipeline.prompt import load_template, render_prompt
    prompt = render_prompt(
        load_template(),
        game_lore_world="Skyrim",
        game_context_lore_summary="Tamriel politics",
        mod_context_name="Demo Mod",
        mod_context_theme="Quest mod",
        style_directives="Concise",
        record_signature_context="",
        glossary_subset_rendered="",
        do_not_translate_list="",
    )
    assert "{{P0}}" in prompt
