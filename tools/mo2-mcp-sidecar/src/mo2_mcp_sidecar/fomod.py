"""FOMOD parsing JSON-RPC methods (pyfomod wrapper).

Task 27 adds fomod.parse_choices (return full step/group/option tree).
Task 28 adds fomod.resolve_files (consume choices -> file mapping).

Lane V3 FOMOD-EXT (2026-06-17): adds optional `mo2_state` parameter to both
methods. When supplied, `parse_choices` surfaces `dependencies_status` on each
page / option (and `module_dependencies_status` at top level) reporting whether
the FOMOD's `<moduleDependencies>` / `<visible>` / `<dependencyType>` clauses
hold against current MO2 state — so agents can see at PLAN TIME which options
will be blocked before they pick choices. `resolve_files` propagates state into
pyfomod's Installer constructor so `game_version` and `file_type` checks fire
naturally during the wizard walk.

A `conditional_pages_note` flag is always returned (independent of mo2_state)
flagging static-tree-vs-actual-wizard-flow divergence: when the FOMOD has any
conditional pages, conditional file patterns, or dynamic option types, the
static page dump may include pages the wizard will hide. See
`fomod_deps.detect_conditional_flow` for the exact heuristic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .envelope import register_method

try:
    import pyfomod
    _PYFOMOD_AVAILABLE = True
except ImportError:
    _PYFOMOD_AVAILABLE = False

from .fomod_deps import (
    collect_dynamic_option_clauses,
    detect_conditional_flow,
    evaluate_conditions,
    make_file_type_callback,
    normalize_mo2_state,
)


_CONDITIONAL_PAGES_NOTE = (
    "This FOMOD declares conditional pages, conditional file installs, or "
    "dynamic option types. The static page tree returned here may include "
    "pages the wizard would hide given the current MO2 state. To choose "
    "defensively, supply choices for every page; the wizard will skip those "
    "whose <visible> conditions don't hold. A future enhancement (v1.4+) may "
    "expose a wizard-step API."
)


def _option_type_name(opt: Any) -> str:
    """Extract pyfomod OptionType display string (Optional/Required/Recommended/NotUsable/CouldBeUsable)."""
    t = getattr(opt, "type", None)
    if t is None:
        return "Optional"
    # pyfomod enums store the human-readable name in .value, not .name
    return getattr(t, "value", str(t))


def _group_type_name(group: Any) -> str:
    """Extract pyfomod GroupType display string (SelectAtLeastOne/SelectAtMostOne/SelectExactlyOne/SelectAny/SelectAll)."""
    t = getattr(group, "type", None)
    if t is None:
        return "SelectAny"
    # pyfomod enums store the human-readable name in .value, not .name
    return getattr(t, "value", str(t))


def _option_payload(opt: Any, mo2_state: dict[str, Any] | None) -> dict[str, Any]:
    """Build the per-option dict. Adds dependencies_status when mo2_state given."""
    image = getattr(opt, "image", None)
    payload = {
        "name": getattr(opt, "name", ""),
        "description": getattr(opt, "description", "") or "",
        "image": str(image) if image else None,
        "type": _option_type_name(opt),
    }
    if mo2_state is None:
        return payload

    # Dynamic option type (Type) — resolve against mo2_state to compute the
    # effective type and dependency status.
    from pyfomod import Type
    if isinstance(getattr(opt, "type", None), Type):
        met, missing, resolved_type = collect_dynamic_option_clauses(opt, mo2_state)
        payload["type"] = resolved_type
        payload["dependencies_status"] = {"met": met, "missing": missing}
    else:
        payload["dependencies_status"] = {"met": True, "missing": []}
    return payload


def _page_payload(page: Any, mo2_state: dict[str, Any] | None) -> dict[str, Any]:
    groups = []
    for group in page:
        options = [_option_payload(opt, mo2_state) for opt in group]
        groups.append({
            "name": getattr(group, "name", ""),
            "type": _group_type_name(group),
            "options": options,
        })
    payload: dict[str, Any] = {"name": getattr(page, "name", ""), "groups": groups}
    if mo2_state is not None:
        page_conditions = getattr(page, "conditions", None)
        met, missing = evaluate_conditions(page_conditions, mo2_state)
        payload["dependencies_status"] = {"met": met, "missing": missing}
    return payload


def fomod_parse_choices(params: dict) -> dict:
    """Parse a FOMOD installer's info.xml + ModuleConfig.xml; return the step/group/option tree.

    Args:
        params["archive_path"]: path to extracted FOMOD root (must contain fomod/ subdirectory).
        params["mo2_state"]: (Lane V3, optional) dict with shape
            {
              "enabled_plugins": [str],   # plugin filenames present + enabled
              "game_version": str | None, # LooseVersion-comparable string
              "provided_files": [str],    # any provided file paths (for non-plugin <fileDependency>)
            }
            When supplied, the response gains `dependencies_status` per page/option
            and `module_dependencies_status` at top level reflecting whether each
            FOMOD `<dependencies>` clause holds against current MO2 state.

    Returns:
        {
          "fomod_name": str,
          "fomod_version": str | None,
          "conditional_pages_note": str | None,
          "module_dependencies_status": {met, missing} | None,
          "pages": [
            {
              "name": str,
              "dependencies_status": {met, missing} | None,
              "groups": [
                {"name": str, "type": str, "options": [
                  {"name": str, "description": str, "image": str | None, "type": str,
                   "dependencies_status": {met, missing} | None}
                ]}
              ]
            }
          ]
        }

    Backward compat: when `mo2_state` is omitted, per-page / per-option
    `dependencies_status` and top-level `module_dependencies_status` are all
    omitted (not present in the dict). `conditional_pages_note` is always
    returned (None if no conditional flow detected, string otherwise).

    Raises:
        RuntimeError("pyfomod_not_available") if pyfomod cannot be imported.
        FileNotFoundError if archive_path doesn't exist.
        RuntimeError("not_a_fomod") if pyfomod cannot parse the directory.
    """
    if not _PYFOMOD_AVAILABLE:
        raise RuntimeError("pyfomod_not_available")

    archive_path = Path(params["archive_path"])
    if not archive_path.exists():
        raise FileNotFoundError(f"archive not found: {archive_path}")

    import shutil
    import tempfile
    from .archive import archive_extract_all

    scratch_dir: Path | None = None
    parse_root = archive_path
    if archive_path.is_file():
        scratch_dir = Path(tempfile.mkdtemp(prefix="fomod-parse-"))
        archive_extract_all({
            "archive_path": str(archive_path),
            "dest": str(scratch_dir),
        })
        parse_root = scratch_dir

    try:
        root = pyfomod.parse(str(parse_root))
    except Exception as exc:
        raise RuntimeError(f"not_a_fomod: {exc}")
    finally:
        if scratch_dir is not None:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    raw_mo2_state = params.get("mo2_state")
    mo2_state = normalize_mo2_state(raw_mo2_state) if raw_mo2_state is not None else None

    pages = [_page_payload(page, mo2_state) for page in (getattr(root, "pages", []) or [])]

    has_conditional_flow = detect_conditional_flow(root)
    note = _CONDITIONAL_PAGES_NOTE if has_conditional_flow else None

    version = getattr(root, "version", None)
    result: dict[str, Any] = {
        "fomod_name": getattr(root, "name", "") or "",
        "fomod_version": str(version) if version else None,
        "conditional_pages_note": note,
        "pages": pages,
    }

    if mo2_state is not None:
        module_conditions = getattr(root, "conditions", None)
        met, missing = evaluate_conditions(module_conditions, mo2_state)
        result["module_dependencies_status"] = {"met": met, "missing": missing}

    return result


def fomod_resolve_files(params: dict) -> dict:
    """Apply user choices to a FOMOD installer and return the resolved file mapping.

    pyfomod Installer is wizard-style: next() starts/advances pages, files() at end.
    We walk pages via next(), matching user choices to InstallerOption objects.

    Args:
        params["archive_path"]: path to extracted FOMOD root
        params["choices"]: list of {page_name, selected_options: [{group_name, option_name}]}
        params["mo2_state"]: (Lane V3, optional) dict — see fomod_parse_choices.
            When supplied, `game_version` is forwarded to Installer for
            <gameDependency> checks, and a file_type callback derived from
            enabled_plugins+provided_files is forwarded for <fileDependency>
            checks. pyfomod's Installer will raise FailedCondition (surfaced as
            invalid_choices: ...) if the user picks an option whose conditions
            don't hold OR if the FOMOD's <moduleDependencies> don't hold.

    Returns:
        {
          "files": [{"source": str, "destination": str}],
          "file_count": int,
        }

    Raises:
        RuntimeError("pyfomod_not_available")
        RuntimeError("invalid_choices: <reason>") if pyfomod rejects choices.
    """
    if not _PYFOMOD_AVAILABLE:
        raise RuntimeError("pyfomod_not_available")

    archive_path = Path(params["archive_path"])
    if not archive_path.exists():
        raise FileNotFoundError(f"archive not found: {archive_path}")
    choices = params.get("choices", [])
    if not isinstance(choices, list):
        raise RuntimeError("invalid_choices: choices must be a list")

    try:
        root = pyfomod.parse(str(archive_path))
    except Exception as exc:
        raise RuntimeError(f"not_a_fomod: {exc}")

    raw_mo2_state = params.get("mo2_state")
    mo2_state = normalize_mo2_state(raw_mo2_state) if raw_mo2_state is not None else None

    # Build lookup: page_name -> group_name -> set of selected option names
    by_page: dict[str, dict[str, set[str]]] = {}
    for ch in choices:
        if not isinstance(ch, dict):
            continue
        page_name = ch.get("page_name", "")
        groups = by_page.setdefault(page_name, {})
        for sel in ch.get("selected_options", []) or []:
            if not isinstance(sel, dict):
                continue
            group_name = sel.get("group_name", "")
            opt_name = sel.get("option_name", "")
            groups.setdefault(group_name, set()).add(opt_name)

    installer_kwargs: dict[str, Any] = {"path": str(archive_path)}
    if mo2_state is not None:
        if mo2_state["game_version"] is not None:
            installer_kwargs["game_version"] = mo2_state["game_version"]
        file_type_cb = make_file_type_callback(mo2_state)
        if file_type_cb is not None:
            installer_kwargs["file_type"] = file_type_cb

    try:
        installer = pyfomod.Installer(root, **installer_kwargs)
    except Exception as exc:
        # Installer constructor calls _test_conditions(root.conditions) and
        # raises FailedCondition if module-level dependencies aren't met. We
        # surface that as invalid_choices since it's the same agent-facing
        # failure shape (the install can't proceed).
        raise RuntimeError(f"invalid_choices: module dependencies unmet: {exc}")

    try:
        page = installer.next()  # start at page 0
        while page is not None:
            wanted_by_group = by_page.get(getattr(page, "name", ""), {})
            selected: list[Any] = []
            for group in page:
                wanted = wanted_by_group.get(getattr(group, "name", ""), set())
                for opt in group:
                    if getattr(opt, "name", "") in wanted:
                        selected.append(opt)
            page = installer.next(selected_options=selected)
    except Exception as exc:
        raise RuntimeError(f"invalid_choices: {exc}")

    # installer.files() returns dict[str, str]: source → destination
    resolved = installer.files()
    files = [{"source": str(k), "destination": str(v)} for k, v in resolved.items()]

    return {"files": files, "file_count": len(files)}


def register() -> None:
    register_method("fomod.parse_choices", fomod_parse_choices)
    register_method("fomod.resolve_files", fomod_resolve_files)
