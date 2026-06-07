"""System prompt template rendering ownership."""

# ruff: noqa: RUF001

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from bgs_translator.config import paths


@dataclass
class PromptTemplate:
    """A named system-prompt template."""

    name: str
    template: str
    required_slots: list[str]
    optional_slots: list[str]


REQUIRED_SLOTS = [
    "game_lore_world",
    "game_context_lore_summary",
    "mod_context_name",
    "mod_context_theme",
    "style_directives",
    "glossary_subset_rendered",
    "do_not_translate_list",
]

OPTIONAL_SLOTS = [
    "parent_context_summary_if_present",
    "ad_hoc_context_if_present",
]

DEFAULT_TEMPLATE = """你是 ${game_lore_world} 的本地化译者。

游戏世界：${game_context_lore_summary}
mod：${mod_context_name} —— ${mod_context_theme}
${parent_context_summary_if_present}

风格要求：
${style_directives}

补充上下文：
${ad_hoc_context_if_present}

术语表（必须严格遵循）：
${glossary_subset_rendered}

禁止翻译（保持原文）：
${do_not_translate_list}

注意：占位符 {{P0}}, {{P1}}, ... 不要翻译、不要删除、不要增加。
返回 JSON 格式 {"I1": "译文", "I2": "译文", ...}
"""


def load_template(name: str = "default") -> PromptTemplate:
    """Load a configured prompt template, falling back to the built-in default."""

    template_path = paths.prompt_templates_root() / f"{name}.md"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else DEFAULT_TEMPLATE
    ok, problems = validate_template(template)
    if not ok:
        msg = f"Invalid prompt template {name}: {'; '.join(problems)}"
        raise ValueError(msg)
    return PromptTemplate(
        name=name,
        template=template,
        required_slots=list(REQUIRED_SLOTS),
        optional_slots=list(OPTIONAL_SLOTS),
    )


def validate_template(template: str) -> tuple[bool, list[str]]:
    """Validate slot coverage and Template syntax."""

    problems: list[str] = []
    referenced = _referenced_slots(template)
    allowed = set(REQUIRED_SLOTS) | set(OPTIONAL_SLOTS)
    problems.extend(f"missing required slot: {slot}" for slot in REQUIRED_SLOTS if slot not in referenced)
    problems.extend(f"unknown slot: {slot}" for slot in sorted(referenced - allowed))
    try:
        Template(template).substitute(dict.fromkeys(allowed, ""))
    except (KeyError, ValueError) as exc:
        problems.append(f"template syntax error: {exc}")
    return len(problems) == 0, problems


def render_prompt(
    template: PromptTemplate,
    *,
    game_lore_world: str,
    game_context_lore_summary: str,
    mod_context_name: str,
    mod_context_theme: str,
    style_directives: str,
    glossary_subset_rendered: str,
    do_not_translate_list: str,
    parent_context_summary: str | None = None,
    ad_hoc_context: str | None = None,
) -> str:
    """Render a system prompt with optional lines removed when empty."""

    raw_template = _omit_empty_optional_lines(
        template.template,
        parent_context_summary=parent_context_summary,
        ad_hoc_context=ad_hoc_context,
    )
    data = {
        "game_lore_world": game_lore_world,
        "game_context_lore_summary": game_context_lore_summary,
        "mod_context_name": mod_context_name,
        "mod_context_theme": mod_context_theme,
        "style_directives": style_directives,
        "glossary_subset_rendered": glossary_subset_rendered,
        "do_not_translate_list": do_not_translate_list,
        "parent_context_summary_if_present": parent_context_summary or "",
        "ad_hoc_context_if_present": ad_hoc_context or "",
    }
    return Template(raw_template).substitute(data)


def _omit_empty_optional_lines(
    template: str,
    *,
    parent_context_summary: str | None,
    ad_hoc_context: str | None,
) -> str:
    lines = template.splitlines()
    rendered_lines: list[str] = []
    for line in lines:
        if not parent_context_summary and "${parent_context_summary_if_present}" in line:
            continue
        if not ad_hoc_context and "${ad_hoc_context_if_present}" in line:
            if rendered_lines and rendered_lines[-1].strip() in {"补充上下文：", "Supplemental context:"}:
                rendered_lines.pop()
            continue
        rendered_lines.append(line)
    suffix = "\n" if template.endswith("\n") else ""
    return "\n".join(rendered_lines) + suffix


def _referenced_slots(template: str) -> set[str]:
    referenced: set[str] = set()
    for match in Template.pattern.finditer(template):
        named = match.group("named") or match.group("braced")
        if named:
            referenced.add(named)
        elif match.group("invalid") is not None:
            referenced.add("<invalid>")
    return referenced


__all__ = [
    "DEFAULT_TEMPLATE",
    "OPTIONAL_SLOTS",
    "REQUIRED_SLOTS",
    "PromptTemplate",
    "load_template",
    "render_prompt",
    "validate_template",
]
