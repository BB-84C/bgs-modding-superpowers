"""Extract cpTranslate schema slices from xEdit Pascal wbDefinitions files.

This is a standalone build utility. It intentionally uses a pragmatic scanner
instead of a full Pascal parser because the generated YAML is reviewed and
committed as a first-class artifact.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

PARSER_VERSION = "1.0.0"
DEFAULT_BYTE_BUDGET = 65520
FORM_VERSION_RANGES: dict[str, tuple[int, int]] = {
    "Oblivion": (0, 0),
    "Fallout3": (0, 0),
    "FalloutNV": (0, 0),
    "SkyrimLE": (43, 43),
    "SkyrimSE": (43, 44),
    "Fallout4": (131, 131),
    "Fallout76": (131, 250),
    "Starfield": (552, 576),
}
LIST_INDEX_BY_SIG: dict[str, int] = {
    "DESC": 1,
    "NAM1": 2,
}
KNOWN_MULTI_VALUE_SIGS = {
    "ITXT",
    "NAM1",
    "NNAM",
    "BTXT",
    "CNAM",
    "ISTX",
    "QMDP",
    "QMDS",
    "QMDT",
    "QMSU",
}


@dataclass(frozen=True)
class Field:
    subrecord_sig: str
    list_index: int = 0
    byte_budget: int = DEFAULT_BYTE_BUDGET
    multi_value: bool = False
    notes: str = ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--game", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--form-version-range", nargs=2, type=int, metavar=("LOW", "HIGH"))
    args = parser.parse_args()

    if not args.source.exists():
        print(f"source not found: {args.source}", file=sys.stderr)
        return 1

    form_range = tuple(args.form_version_range) if args.form_version_range else FORM_VERSION_RANGES[args.game]
    text = args.source.read_text(encoding="utf-8", errors="replace")
    records, warnings = extract_records(text)
    manifest: dict[str, Any] = {
        "game": args.game,
        "form_version_range": list(form_range),
        "parser_version": PARSER_VERSION,
        "schema_version": f"{_schema_slug(args.game)}-{PARSER_VERSION}",
        "records": {
            sig: [asdict(field) for field in fields]
            for sig, fields in sorted(records.items())
            if fields
        },
    }

    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except OSError as exc:
        print(f"failed to write {args.output}: {exc}", file=sys.stderr)
        return 1

    field_counts = {sig: len(fields) for sig, fields in sorted(records.items()) if fields}
    print(f"records scanned: {extract_records.scanned}", file=sys.stderr)  # type: ignore[attr-defined]
    print(f"cpTranslate fields found: {sum(field_counts.values())}", file=sys.stderr)
    print(f"per-record field count: {field_counts}", file=sys.stderr)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


def extract_records(text: str) -> tuple[dict[str, list[Field]], list[str]]:
    clean = _strip_comments(text)
    shorthands = _extract_shorthands(clean)
    records: dict[str, list[Field]] = {}
    warnings: list[str] = []
    scanned = 0
    for record_sig, block in _iter_record_blocks(clean):
        scanned += 1
        fields: list[Field] = []
        fields.extend(_extract_direct_fields(block))
        for name in sorted(set(re.findall(r"\bwb[A-Za-z0-9_]+\b", block))):
            if name in shorthands:
                fields.append(shorthands[name])
            elif _looks_like_translatable_shorthand(name):
                warnings.append(f"{record_sig}: unresolved shorthand {name}")
        deduped = _dedupe_fields(fields)
        if deduped:
            records[record_sig] = deduped
    extract_records.scanned = scanned  # type: ignore[attr-defined]
    return records, warnings


def _strip_comments(text: str) -> str:
    text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.S)
    text = re.sub(r"\{[^{}]*\}", "", text)
    return re.sub(r"//.*", "", text)


def _extract_shorthands(text: str) -> dict[str, Field]:
    shorthands: dict[str, Field] = {}
    for match in re.finditer(r"(?:^|\s)(?:var\s+)?(wb\w+)\s*:=", text):
        name = match.group(1)
        end = text.find(";", match.end())
        if end == -1:
            continue
        if "function" in text[match.end() : end]:
            func_end = text.find("end;", end)
            if func_end == -1:
                continue
            snippet = text[match.start() : func_end + 4]
        else:
            snippet = text[match.start() : end + 1]
        fields = _extract_direct_fields(snippet)
        if fields:
            shorthands[name] = fields[0]
    return shorthands


def _iter_record_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    offset = 0
    while True:
        start = text.find("wbRecord(", offset)
        if start == -1:
            return blocks
        sig_match = re.match(r"wbRecord\(\s*([A-Za-z0-9_]+)", text[start:])
        if sig_match is None:
            offset = start + len("wbRecord(")
            continue
        record_sig = _normalize_sig(sig_match.group(1))
        end = _find_matching_paren(text, start + len("wbRecord"))
        if end == -1:
            offset = start + len("wbRecord(")
            continue
        blocks.append((record_sig, text[start : end + 1]))
        offset = end + 1


def _find_matching_paren(text: str, open_index: int) -> int:
    depth = 0
    quote: str | None = None
    index = open_index
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _extract_direct_fields(text: str) -> list[Field]:
    fields: list[Field] = []
    for match in re.finditer(r"\b(wb(?:LStringKC|LString|StringKC|StringT|String))\s*\(", text):
        open_index = text.find("(", match.start())
        close_index = _find_matching_paren(text, open_index)
        if close_index == -1:
            continue
        call = text[match.start() : close_index + 1]
        if "cpTranslate" not in call:
            continue
        field = _field_from_call(call)
        if field is not None:
            fields.append(field)
    return fields


def _field_from_call(call: str) -> Field | None:
    args = _split_args(call[call.find("(") + 1 : call.rfind(")")])
    if not args:
        return None
    sig = _extract_sig(args[0])
    if sig is None:
        return None
    explicit_index = _last_integer_before_cptranslate(args)
    list_index = LIST_INDEX_BY_SIG.get(sig, explicit_index)
    return Field(
        subrecord_sig=sig,
        list_index=list_index,
        multi_value=sig in KNOWN_MULTI_VALUE_SIGS,
        notes="voice-linked" if sig == "NAM1" else "",
    )


def _split_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(args):
        char = args[index]
        if quote is not None:
            if char == quote:
                if index + 1 < len(args) and args[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
        index += 1
    parts.append(args[start:].strip())
    return parts


def _extract_sig(token: str) -> str | None:
    token = token.strip()
    quoted = re.fullmatch(r"'([^']+)'", token)
    if quoted:
        raw = quoted.group(1)
        return _normalize_sig(raw) if _is_sig(raw) else None
    if _is_sig(token):
        return _normalize_sig(token)
    if "_" in token:
        tail = token.rsplit("_", 1)[-1]
        if _is_sig(tail):
            return _normalize_sig(tail)
    return None


def _normalize_sig(sig: str) -> str:
    return sig.strip().upper().replace("'", "")[:4]


def _is_sig(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]{4}", token.strip()))


def _last_integer_before_cptranslate(args: list[str]) -> int:
    cp_index = next((idx for idx, arg in enumerate(args) if "cpTranslate" in arg), len(args))
    for arg in reversed(args[:cp_index]):
        if re.fullmatch(r"\d+", arg):
            return int(arg)
    return 0


def _looks_like_translatable_shorthand(name: str) -> bool:
    return bool(re.search(r"(?:FULL|DESC|DESCRIPTION|NAME|ATTX)", name, re.I))


def _dedupe_fields(fields: list[Field]) -> list[Field]:
    by_key: dict[tuple[str, int], Field] = {}
    counts = Counter((field.subrecord_sig, field.list_index) for field in fields)
    for field in fields:
        key = (field.subrecord_sig, field.list_index)
        if key in by_key:
            existing = by_key[key]
            by_key[key] = Field(
                existing.subrecord_sig,
                existing.list_index,
                existing.byte_budget,
                existing.multi_value or counts[key] > 1,
                existing.notes,
            )
        else:
            by_key[key] = field
    return sorted(by_key.values(), key=lambda field: (field.subrecord_sig, field.list_index))


def _schema_slug(game: str) -> str:
    slug_map = {
        "Oblivion": "oblivion",
        "Fallout3": "fo3",
        "FalloutNV": "fnv",
        "SkyrimLE": "skyrim_le",
        "SkyrimSE": "skyrim_se",
        "Fallout4": "fo4",
        "Fallout76": "fo76",
        "Starfield": "starfield",
    }
    return slug_map.get(game, game.lower())


if __name__ == "__main__":
    raise SystemExit(main())
