"""Post-LLM validation gate ownership."""

from __future__ import annotations

import re

from pydantic import BaseModel

from bgs_translator.pipeline.mask import MaskedUnit, unmask_dest


class ValidationFailure(BaseModel):
    """One validation gate failure or soft warning."""

    item_id: str
    gate: str
    reason: str
    soft: bool


class ValidationResult(BaseModel):
    """Validation result for a single item."""

    item_id: str
    ok: bool
    failures: list[ValidationFailure]


GATES = [
    "mask_completeness",
    "pair_nesting",
    "no_hallucinated_placeholders",
    "byte_budget",
    "encoding_feasibility",
    "do_not_translate_intact",
    "mcm_key_intact",
    "length_sanity",
    "empty_dest_for_nonempty_source",
]

_PLACEHOLDER_RE = re.compile(r"\{\{P\d+\}\}")


def validate_item(
    masked_unit: MaskedUnit,
    dest_masked: str,
    do_not_translate_terms: list[str],
    target_encoding_chain: list[str],
) -> ValidationResult:
    """Run validation gates in order, returning the first hard failure."""

    item_id = _item_id(masked_unit)
    hard_failure = _empty_dest_for_nonempty_source(item_id, masked_unit.unit.source, dest_masked)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])
    hard_failure = _mask_completeness(item_id, masked_unit, dest_masked)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])
    hard_failure = _pair_nesting(item_id, masked_unit, dest_masked)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])
    hard_failure = _no_hallucinated_placeholders(item_id, masked_unit, dest_masked)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])

    unmasked = unmask_dest(dest_masked, masked_unit.mask_map, masked_unit.mcm_token_prefix)
    hard_failure = _byte_budget(item_id, masked_unit, unmasked)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])
    hard_failure = _encoding_feasibility(item_id, unmasked, target_encoding_chain)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])
    hard_failure = _do_not_translate_intact(
        item_id, masked_unit.unit.source, unmasked, do_not_translate_terms
    )
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])
    hard_failure = _mcm_key_intact(item_id, masked_unit, dest_masked)
    if hard_failure is not None:
        return ValidationResult(item_id=item_id, ok=False, failures=[hard_failure])

    soft_warning = _length_sanity(item_id, masked_unit.unit.source, unmasked)
    failures = [] if soft_warning is None else [soft_warning]
    return ValidationResult(item_id=item_id, ok=True, failures=failures)


def _mask_completeness(
    item_id: str, masked_unit: MaskedUnit, dest_masked: str
) -> ValidationFailure | None:
    for token in masked_unit.mask_map.values():
        if token.must_appear_count >= 1 and dest_masked.count(token.placeholder) < token.must_appear_count:
            return ValidationFailure(
                item_id=item_id,
                gate="mask_completeness",
                reason=(
                    f"placeholder {token.placeholder} (which represents {token.original!r}) "
                    f"must appear at least {token.must_appear_count} time(s)"
                ),
                soft=False,
            )
    return None


def _pair_nesting(
    item_id: str, masked_unit: MaskedUnit, dest_masked: str
) -> ValidationFailure | None:
    open_tokens = [token for token in masked_unit.mask_map.values() if token.kind == "tag_open_font"]
    close_tokens = [token for token in masked_unit.mask_map.values() if token.kind == "tag_close_font"]
    if len(open_tokens) != len(close_tokens):
        return ValidationFailure(
            item_id=item_id,
            gate="pair_nesting",
            reason="font tag placeholder pairs are unbalanced",
            soft=False,
        )
    for open_token, close_token in zip(open_tokens, close_tokens, strict=True):
        open_pos = dest_masked.find(open_token.placeholder)
        close_pos = dest_masked.find(close_token.placeholder)
        if open_pos == -1 or close_pos == -1 or open_pos > close_pos:
            return ValidationFailure(
                item_id=item_id,
                gate="pair_nesting",
                reason=f"{open_token.placeholder} must appear before {close_token.placeholder}",
                soft=False,
            )
    return None


def _no_hallucinated_placeholders(
    item_id: str, masked_unit: MaskedUnit, dest_masked: str
) -> ValidationFailure | None:
    allowed = set(masked_unit.mask_map)
    for placeholder in _PLACEHOLDER_RE.findall(dest_masked):
        if placeholder not in allowed:
            return ValidationFailure(
                item_id=item_id,
                gate="no_hallucinated_placeholders",
                reason=f"hallucinated placeholder {placeholder}",
                soft=False,
            )
    return None


def _byte_budget(item_id: str, masked_unit: MaskedUnit, unmasked: str) -> ValidationFailure | None:
    byte_len = len(unmasked.encode("utf-8"))
    if byte_len > masked_unit.byte_budget:
        return ValidationFailure(
            item_id=item_id,
            gate="byte_budget",
            reason=f"UTF-8 byte length {byte_len} exceeds budget {masked_unit.byte_budget}",
            soft=False,
        )
    return None


def _encoding_feasibility(
    item_id: str, unmasked: str, encodings: list[str]
) -> ValidationFailure | None:
    for char in unmasked:
        if not any(_char_encodable(char, encoding) for encoding in encodings):
            return ValidationFailure(
                item_id=item_id,
                gate="encoding_feasibility",
                reason=f"character {char!r} is not encodable in target chain",
                soft=False,
            )
    return None


def _do_not_translate_intact(
    item_id: str, source: str, dest: str, terms: list[str]
) -> ValidationFailure | None:
    source_fold = source.casefold()
    dest_fold = dest.casefold()
    for term in terms:
        term_fold = term.casefold()
        if term_fold in source_fold and term_fold not in dest_fold:
            return ValidationFailure(
                item_id=item_id,
                gate="do_not_translate_intact",
                reason=f"do-not-translate term {term!r} appeared in source but not destination",
                soft=False,
            )
    return None


def _mcm_key_intact(
    item_id: str, masked_unit: MaskedUnit, dest_masked: str
) -> ValidationFailure | None:
    prefix = masked_unit.mcm_token_prefix
    if prefix is not None and not dest_masked.startswith(prefix):
        return ValidationFailure(
            item_id=item_id,
            gate="mcm_key_intact",
            reason=f"destination must start with MCM key prefix {prefix!r}",
            soft=False,
        )
    return None


def _empty_dest_for_nonempty_source(
    item_id: str,
    source: str,
    dest: str,
) -> ValidationFailure | None:
    if source.strip() and not dest.strip():
        return ValidationFailure(
            item_id=item_id,
            gate="empty_dest_for_nonempty_source",
            reason="empty_completion",
            soft=False,
        )
    return None


def _length_sanity(item_id: str, source: str, dest: str) -> ValidationFailure | None:
    if not source:
        return None
    ratio = len(dest) / len(source)
    if ratio < 0.3 or ratio > 3.0:
        return ValidationFailure(
            item_id=item_id,
            gate="length_sanity",
            reason=f"destination/source length ratio {ratio:.2f} outside [0.3, 3.0]",
            soft=True,
        )
    return None


def _char_encodable(char: str, encoding: str) -> bool:
    candidates = [encoding]
    if encoding.endswith("-custom"):
        candidates.append(encoding.removesuffix("-custom"))
    for candidate in candidates:
        try:
            char.encode(candidate)
            return True
        except (LookupError, UnicodeEncodeError):
            continue
    return False


def _item_id(masked_unit: MaskedUnit) -> str:
    raw_item_id = getattr(masked_unit, "item_id", None)
    if isinstance(raw_item_id, str) and raw_item_id:
        return raw_item_id
    return "I1"


__all__ = ["GATES", "ValidationFailure", "ValidationResult", "validate_item"]
