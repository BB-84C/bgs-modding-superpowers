from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


VALIDATED = {
    "lock_guard_block": True,
    "try_lock_guard_block": True,
    "guard_declaration_protects_function_logic": True,
}


@dataclass(frozen=True)
class Rule:
    name: str
    detect_regex: re.Pattern[str]
    rewrite_fn: Callable[[re.Match[str]], str]
    validated_default: bool = False


def fix(psc_text: str, *, validated: dict | None = None) -> str:
    active = dict(VALIDATED)
    if validated:
        active.update(validated)

    text = psc_text
    for rule in RULES:
        if active.get(rule.name, rule.validated_default):
            text = _apply_validated_rule(text, rule)
        else:
            text = _mark_unverified_rule(text, rule)
    if active.get("guard_declaration_protects_function_logic", False):
        text = _fix_guard_declarations(text)
    return text


def _apply_validated_rule(text: str, rule: Rule) -> str:
    def replace(match: re.Match[str]) -> str:
        rewritten = rule.rewrite_fn(match)
        marker = f"; bgs-papyrus: sf-syntax-fix applied ({rule.name})\n"
        if _has_nearby_marker(text, match.start(), marker.strip()):
            return rewritten
        return marker + rewritten

    return rule.detect_regex.sub(replace, text)


def _mark_unverified_rule(text: str, rule: Rule) -> str:
    def replace(match: re.Match[str]) -> str:
        marker = f"; UNVERIFIED sf-syntax: {rule.name}\n"
        if _has_nearby_marker(text, match.start(), marker.strip()):
            return match.group(0)
        return marker + match.group(0)

    return rule.detect_regex.sub(replace, text)


def _has_nearby_marker(text: str, position: int, marker_text: str) -> bool:
    line_start = text.rfind("\n", 0, position) + 1
    previous_line_end = max(0, line_start - 1)
    previous_line_start = text.rfind("\n", 0, previous_line_end) + 1
    nearby = text[previous_line_start:line_start]
    return marker_text in nearby


def _rewrite_lock_guard(match: re.Match[str]) -> str:
    return f"{match.group('indent')}LockGuard{match.group('rest')}{match.group('body')}{match.group('endindent')}EndLockGuard"


def _rewrite_try_lock_guard(match: re.Match[str]) -> str:
    return f"{match.group('indent')}TryLockGuard{match.group('rest')}{match.group('body')}{match.group('endindent')}EndTryLockGuard"


def _fix_guard_declarations(text: str) -> str:
    locked_guards = _locked_guard_names(text)
    member_guards = {name.lower() for name in re.findall(r"(?i)RequiresGuard\(([^)]+)\)", text)}
    if not locked_guards:
        return text

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    declaration_warning_seen = False
    declaration = re.compile(r"^(?P<indent>[ \t]*)Guard\s+(?P<name>\w+)\s*(?P<tail>(?:;.*)?)$", re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        if "Guard declaration syntax is EXPERIMENTAL" in stripped:
            declaration_warning_seen = True
            out.append(line)
            continue

        newline = "\n" if line.endswith("\n") else ""
        content = line[:-1] if newline else line
        match = declaration.match(content)
        name = match.group("name") if match else ""
        if declaration_warning_seen and match and name.lower() in locked_guards and name.lower() not in member_guards:
            tail = match.group("tail")
            spacer = " " if tail else ""
            out.append(f"{match.group('indent')}Guard {name} ProtectsFunctionLogic{spacer}{tail}{newline}")
        else:
            out.append(line)
        declaration_warning_seen = False
    return "".join(out)


def _locked_guard_names(text: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"(?im)^\s*(?:Try)?LockGuard\s*\(?\s*([^\n;)]+)", text):
        for raw in match.group(1).split(","):
            name = raw.strip().split()[0] if raw.strip() else ""
            if name:
                names.add(name.lower())
    return names


RULES = (
    Rule(
        name="try_lock_guard_block",
        detect_regex=re.compile(
            r"^(?P<indent>[ \t]*)TryGuard(?P<rest>[^\n]*Experimental syntax, may be incorrect: TryGuard[^\n]*\n)(?P<body>.*?)(?P<endindent>^[ \t]*)EndGuard",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        ),
        rewrite_fn=_rewrite_try_lock_guard,
    ),
    Rule(
        name="lock_guard_block",
        detect_regex=re.compile(
            r"^(?P<indent>[ \t]*)Guard(?P<rest>[^\n]*Experimental syntax, may be incorrect: Guard[^\n]*\n)(?P<body>.*?)(?P<endindent>^[ \t]*)EndGuard",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        ),
        rewrite_fn=_rewrite_lock_guard,
    ),
)
