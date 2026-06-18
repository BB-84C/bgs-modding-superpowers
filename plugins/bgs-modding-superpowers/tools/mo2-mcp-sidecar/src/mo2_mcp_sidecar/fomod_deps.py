"""FOMOD dependency evaluation against MO2 state (Lane V3 FOMOD-EXT phase 1+2).

pyfomod's Installer evaluates `<moduleDependencies>` / `<visible>` page conditions
/ `<dependencyType>` option conditions via `Installer._test_conditions`, but it
RAISES `FailedCondition` instead of returning a structured met/missing report —
and its constructor itself raises if `root.conditions` is unmet, so we can't even
use it for static dependency reporting on a FOMOD whose module-level deps don't
hold.

This module provides a standalone evaluator that mirrors pyfomod's condition
semantics (see installer.py:_test_conditions / _test_file_condition /
_test_flag_condition / _test_version_condition) but returns
`(met: bool, missing: list[str])` instead of raising. It's used by
fomod.fomod_parse_choices to surface `dependencies_status` per page / option /
module without aborting on the first failure.

Dependency-evaluation API
-------------------------

`evaluate_conditions(conditions, mo2_state, flags=None) -> (met, missing)`

Where `mo2_state` is the dict shape:

    {
        "enabled_plugins": set[str],   # lowercase plugin filenames, e.g. {"dlccoast.esm"}
        "game_version": str | None,    # LooseVersion-comparable string, e.g. "1.10.163.0"
        "provided_files": set[str],    # lowercase posix paths the enabled mods provide;
                                       # used for non-plugin <fileDependency file="..."/>
    }

And `flags` is the FOMOD-internal flag dict (set by previously-selected options
during a wizard flow). For static `parse_choices` evaluation we treat it as
empty: a `<flagDependency>` whose flag was never set is reported as missing.
"""
from __future__ import annotations

from typing import Any, Iterable

try:
    import pyfomod
    from pyfomod import (
        Conditions,
        ConditionType,
        FileType,
    )
    _PYFOMOD_AVAILABLE = True
except ImportError:
    _PYFOMOD_AVAILABLE = False


# ---------------------------------------------------------------------------
# State normalization helpers (used by both parse and resolve paths)
# ---------------------------------------------------------------------------

def normalize_mo2_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce a caller-supplied `mo2_state` dict into the internal shape.

    Returns the always-present internal shape (with empty sets when the caller
    omitted a key). Lowercases all plugin / file path entries so subsequent
    membership tests are case-insensitive (NTFS default + Bethesda's
    case-insensitive plugin handling).
    """
    if not isinstance(raw, dict):
        return {
            "enabled_plugins": set(),
            "game_version": None,
            "provided_files": set(),
        }

    enabled_plugins = raw.get("enabled_plugins") or []
    if not isinstance(enabled_plugins, (list, tuple, set, frozenset)):
        enabled_plugins = []
    provided_files = raw.get("provided_files") or []
    if not isinstance(provided_files, (list, tuple, set, frozenset)):
        provided_files = []
    game_version = raw.get("game_version") or None
    if game_version is not None and not isinstance(game_version, str):
        game_version = str(game_version)

    def _norm_path(p: str) -> str:
        return str(p).replace("\\", "/").lstrip("/").lower()

    return {
        "enabled_plugins": {str(p).lower() for p in enabled_plugins if p},
        "provided_files": {_norm_path(p) for p in provided_files if p},
        "game_version": game_version,
    }


# ---------------------------------------------------------------------------
# pyfomod-compatible file_type callable
# ---------------------------------------------------------------------------

def _is_plugin_filename(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".esp") or lower.endswith(".esm") or lower.endswith(".esl")


def make_file_type_callback(mo2_state: dict[str, Any]):
    """Return a callable `(file_name: str) -> pyfomod.FileType` for Installer.

    Mirrors how MO2 / xEdit see file state:
      - Plugin file (.esp/.esm/.esl) AND enabled in plugins.txt -> ACTIVE
      - Plugin file present in provided_files but not in plugins.txt -> INACTIVE
      - Non-plugin file present in provided_files -> ACTIVE (loose files in
        enabled mods are always "active" from MO2's VFS perspective; there is
        no "loaded but disabled" state for non-plugin assets)
      - Otherwise -> MISSING

    Pyfomod uses this in `<fileDependency file="X.esp" state="Active|Inactive|Missing"/>`.
    """
    if not _PYFOMOD_AVAILABLE:
        return None
    enabled_plugins = mo2_state["enabled_plugins"]
    provided_files = mo2_state["provided_files"]

    def file_type(file_name: str) -> "FileType":
        norm = str(file_name).replace("\\", "/").lstrip("/").lower()
        base = norm.rsplit("/", 1)[-1]
        if _is_plugin_filename(base):
            if base in enabled_plugins:
                return FileType.ACTIVE
            if norm in provided_files or base in provided_files:
                return FileType.INACTIVE
            return FileType.MISSING
        # Non-plugin file
        if norm in provided_files:
            return FileType.ACTIVE
        return FileType.MISSING

    return file_type


# ---------------------------------------------------------------------------
# Standalone conditions evaluator (mirrors pyfomod._test_conditions semantics)
# ---------------------------------------------------------------------------

def _format_file_missing(file_name: str, want_state: "FileType", actual: "FileType") -> str:
    return f"file {file_name} must be {want_state.value} (was {actual.value})"


def _format_version_missing(required: str, actual: str | None) -> str:
    if actual is None:
        return f"game version {required} required (no version reported)"
    return f"game version {required} required (was {actual})"


def _format_flag_missing(flag_name: str, want_value: str, actual: str | None) -> str:
    if actual is None:
        return f"flag {flag_name} must be {want_value!r} (not set)"
    return f"flag {flag_name} must be {want_value!r} (was {actual!r})"


def evaluate_conditions(
    conditions: "Conditions | None",
    mo2_state: dict[str, Any],
    flags: dict[str, str] | None = None,
) -> tuple[bool, list[str]]:
    """Evaluate a pyfomod Conditions tree against MO2 state, non-raising.

    Returns `(met, missing)` where `missing` is a list of human-readable
    failure descriptions. Empty / falsy conditions => `(True, [])`.

    Mirrors pyfomod's Installer._test_conditions semantics: AND fails on first
    failed clause, OR fails only when all clauses fail.
    """
    if not _PYFOMOD_AVAILABLE:
        return True, []
    if conditions is None or len(conditions) == 0:
        return True, []
    flags = flags or {}

    enabled_plugins = mo2_state["enabled_plugins"]
    provided_files = mo2_state["provided_files"]
    game_version = mo2_state["game_version"]
    file_type_cb = make_file_type_callback(mo2_state)

    op = conditions.type
    failures: list[str] = []
    clause_count = 0

    for key, value in conditions.items():
        clause_count += 1
        clause_failed = False
        clause_msg: str | None = None
        try:
            if key is None:
                # version: key=None, value=version string
                if game_version is None:
                    # pyfomod treats absent version as "no check" — mirror that
                    pass
                else:
                    from distutils.version import LooseVersion
                    if LooseVersion(game_version) < LooseVersion(value):
                        clause_failed = True
                        clause_msg = _format_version_missing(str(value), game_version)
            elif isinstance(key, str):
                if isinstance(value, FileType):
                    if file_type_cb is None:
                        # pyfomod: no file_type cb => skip silently
                        pass
                    else:
                        actual = file_type_cb(key)
                        if actual is not value:
                            clause_failed = True
                            clause_msg = _format_file_missing(key, value, actual)
                elif isinstance(value, str):
                    actual_flag = flags.get(key)
                    if actual_flag != value:
                        clause_failed = True
                        clause_msg = _format_flag_missing(key, value, actual_flag)
            elif isinstance(key, Conditions):
                inner_met, inner_missing = evaluate_conditions(key, mo2_state, flags)
                if not inner_met:
                    clause_failed = True
                    clause_msg = "; ".join(inner_missing) or "nested conditions unmet"
        except Exception as exc:
            # Defensive: surface evaluation errors as failures rather than
            # crashing the whole parse_choices path.
            clause_failed = True
            clause_msg = f"condition evaluation error: {exc}"

        if clause_failed:
            failures.append(clause_msg or "unmet")
            if op is ConditionType.AND:
                # AND short-circuits on first failure (mirrors pyfomod)
                return False, failures

    if op is ConditionType.OR:
        if len(failures) == clause_count and clause_count > 0:
            return False, failures
        return True, []
    # AND: success means no failures
    return (len(failures) == 0), failures


# ---------------------------------------------------------------------------
# Conditional-flow detection (for the conditional_pages_note flag)
# ---------------------------------------------------------------------------

def _option_type_is_dynamic(opt: Any) -> bool:
    """True if the option's type is conditional (Type instance rather than OptionType)."""
    if not _PYFOMOD_AVAILABLE:
        return False
    from pyfomod import OptionType, Type
    t = getattr(opt, "type", None)
    return isinstance(t, Type)


def detect_conditional_flow(root: Any) -> bool:
    """True if this FOMOD's static page tree may diverge from actual wizard flow.

    Returns True when any of:
      - Root has non-empty moduleDependencies (the installer may refuse to start)
      - Any page has non-empty visible conditions (the page may be hidden)
      - Any option has a dependencyType (the option's selectability is conditional)
      - Root has non-empty file_patterns (conditional file installs depending on
        flags/files)
    """
    if not _PYFOMOD_AVAILABLE:
        return False
    if len(getattr(root, "conditions", []) or []) > 0:
        return True
    file_patterns = getattr(root, "file_patterns", None)
    if file_patterns is not None and len(file_patterns) > 0:
        return True
    for page in getattr(root, "pages", []) or []:
        if len(getattr(page, "conditions", []) or []) > 0:
            return True
        for group in page:
            for opt in group:
                if _option_type_is_dynamic(opt):
                    return True
    return False


def collect_dynamic_option_clauses(opt: Any, mo2_state: dict[str, Any]) -> tuple[bool, list[str], str]:
    """Resolve an Option whose .type is a pyfomod Type (dynamic).

    Returns `(met, missing, resolved_type_name)`:
      - resolved_type_name: the OptionType the option will display as given
        mo2_state (e.g. "Required" / "NotUsable" / "Optional"). Mirrors
        InstallerOption's type-resolution loop in pyfomod/installer.py:45-55.
      - met=False when the resolved type is NotUsable (option can't be selected
        because its preconditions aren't met) — missing carries the failed
        condition descriptions from the last evaluated clause.
      - met=True otherwise (option can be selected; may be Required, Recommended,
        Optional, or CouldBeUsable).
    """
    if not _PYFOMOD_AVAILABLE:
        return True, [], "Optional"
    from pyfomod import OptionType, Type
    t = opt.type
    if not isinstance(t, Type):
        # Static type; "Required" means "must be selected" but that's not a
        # dependency failure — just the FOMOD author's choice.
        type_name = getattr(t, "value", str(t)) if t is not None else "Optional"
        return True, [], type_name

    last_missing: list[str] = []
    for conditions, option_type in t.items():
        met, missing = evaluate_conditions(conditions, mo2_state)
        if met:
            type_name = getattr(option_type, "value", str(option_type))
            is_notusable = option_type is OptionType.NOTUSABLE
            return (not is_notusable), ([] if not is_notusable else missing), type_name
        last_missing = missing

    # No pattern matched -> fall back to default
    default_type = t.default
    type_name = getattr(default_type, "value", str(default_type))
    is_notusable = default_type is OptionType.NOTUSABLE
    return (not is_notusable), (last_missing if is_notusable else []), type_name
