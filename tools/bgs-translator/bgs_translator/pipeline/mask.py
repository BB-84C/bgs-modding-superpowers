"""Protected-span tokenization and unmasking ownership."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bgs_translator.parsers.tes4_family import TranslationUnit


@dataclass(frozen=True)
class MaskToken:
    """One protected source span replaced by a stable placeholder."""

    placeholder: str
    original: str
    kind: str
    must_appear_count: int = 1
    position_locked: bool = True
    paired_with: str | None = None


@dataclass(frozen=True)
class MaskedUnit:
    """A translation unit after protected-span masking."""

    unit: TranslationUnit
    source_masked: str
    mask_map: dict[str, MaskToken]
    byte_budget: int = 65520
    skip_llm: bool = False
    skip_reason: str = ""
    mcm_token_prefix: str | None = None


MASK_PATTERNS: list[tuple[str, str, bool, str | None]] = [
    ("format_printf", r"%[-+0-9.# ]*[sdiuoxXeEfgG%]", True, None),
    ("format_brace_named", r"\{[A-Za-z_][A-Za-z0-9_]*\}", True, None),
    ("format_brace_indexed", r"\{\d+\}", True, None),
    ("alias_substitution", r"<Alias[.\w]*=[\w]+>", False, None),
    ("global_substitution", r"<(Global|spell|GameSetting)\.[\w]+>", False, None),
    ("tag_open_font", r"<font[^>]*>", True, "tag_close_font"),
    ("tag_close_font", r"</font>", True, "tag_open_font"),
    ("newline_structural", r"\r?\n", False, None),
]

_COMPILED_MASK_PATTERNS = [
    (kind, re.compile(pattern), position_locked, paired_with)
    for kind, pattern, position_locked, paired_with in MASK_PATTERNS
]
_PLACEHOLDER_RE = re.compile(r"\{\{P\d+\}\}")
_MCM_PREFIX_RE = re.compile(r"^(\$[A-Za-z_]\w*)(\s+)?")


def mask_source(source: str) -> tuple[str, dict[str, MaskToken], str | None]:
    """Apply protected-span mask patterns to ``source``."""

    mcm_prefix, text = _strip_mcm_prefix(source)
    pieces: list[str] = []
    mask_map: dict[str, MaskToken] = {}
    pos = 0
    next_index = 0
    while pos < len(text):
        matched = False
        for kind, regex, position_locked, paired_with in _COMPILED_MASK_PATTERNS:
            match = regex.match(text, pos)
            if match is None:
                continue
            original = match.group(0)
            placeholder = f"{{{{P{next_index}}}}}"
            next_index += 1
            pieces.append(placeholder)
            mask_map[placeholder] = MaskToken(
                placeholder=placeholder,
                original=original,
                kind=kind,
                position_locked=position_locked,
                paired_with=paired_with,
            )
            pos = match.end()
            matched = True
            break
        if not matched:
            pieces.append(text[pos])
            pos += 1
    return "".join(pieces), mask_map, mcm_prefix


def apply_skip_heuristics(source: str) -> str | None:
    """Return a skip reason when ``source`` matches a built-in no-translate rule."""

    if re.fullmatch(r"\w{3,}_\w*", source, flags=re.ASCII):
        return "snake_case"
    if re.fullmatch(r"\w+[A-Z]+[_a-z\d]+[A-Z]+\w+", source, flags=re.ASCII):
        return "camel_case_id"
    if re.fullmatch(r"(?:\r?\n)+", source):
        return "only_line_breaks"
    if len(source) <= 2:
        return "too_short"
    if re.fullmatch(r"[\d%\\.\+\-:]+", source):
        return "numeric_formatting"
    if re.fullmatch(r"(?:\W|\d|\.)*", source):
        return "punctuation_digits"
    if re.match(r"\w*\\\w*", source):
        return "backslash_containing"
    return None


def build_masked_unit(unit: TranslationUnit) -> MaskedUnit:
    """Apply skip heuristics and protected-span masking to ``unit``."""

    skip_reason = apply_skip_heuristics(unit.source)
    if skip_reason is not None:
        return MaskedUnit(
            unit=unit,
            source_masked=unit.source,
            mask_map={},
            skip_llm=True,
            skip_reason=skip_reason,
        )

    source_masked, mask_map, mcm_prefix = mask_source(unit.source)
    if _masked_text_has_no_meaningful_unprotected_text(source_masked):
        return MaskedUnit(
            unit=unit,
            source_masked=source_masked,
            mask_map=mask_map,
            skip_llm=True,
            skip_reason="all_protected",
            mcm_token_prefix=mcm_prefix,
        )
    return MaskedUnit(
        unit=unit,
        source_masked=source_masked,
        mask_map=mask_map,
        mcm_token_prefix=mcm_prefix,
    )


def unmask_dest(
    dest_masked: str,
    mask_map: dict[str, MaskToken],
    mcm_token_prefix: str | None,
) -> str:
    """Restore protected originals, prepend any MCM prefix, and normalize newlines."""

    result = dest_masked
    for placeholder, token in mask_map.items():
        result = result.replace(placeholder, token.original)
    result = _normalize_newlines_to_source(result, mask_map)
    if mcm_token_prefix and not result.startswith(mcm_token_prefix):
        result = f"{mcm_token_prefix}{result}"
    return result


def _strip_mcm_prefix(source: str) -> tuple[str | None, str]:
    match = _MCM_PREFIX_RE.match(source)
    if match is None:
        return None, source
    token, whitespace = match.groups()
    if whitespace is None and match.end() != len(source):
        return None, source
    prefix = f"{token}{whitespace or ''}"
    return prefix, source[match.end() :]


def _masked_text_has_no_meaningful_unprotected_text(source_masked: str) -> bool:
    unprotected = _PLACEHOLDER_RE.sub("", source_masked)
    return re.fullmatch(r"(?:\s|\W|\d|\.)*", unprotected) is not None


def _normalize_newlines_to_source(result: str, mask_map: dict[str, MaskToken]) -> str:
    newline_tokens = [token for token in mask_map.values() if token.kind == "newline_structural"]
    if any("\r\n" in token.original for token in newline_tokens):
        return result.replace("\r\n", "\n").replace("\n", "\r\n")
    return result.replace("\r\n", "\n")


__all__ = [
    "MASK_PATTERNS",
    "MaskToken",
    "MaskedUnit",
    "apply_skip_heuristics",
    "build_masked_unit",
    "mask_source",
    "unmask_dest",
]
