"""FOMOD parsing JSON-RPC methods (pyfomod wrapper).

Task 27 adds fomod.parse_choices (return full step/group/option tree).
Task 28 will add fomod.resolve_files (consume choices -> file mapping).
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


def fomod_parse_choices(params: dict) -> dict:
    """Parse a FOMOD installer's info.xml + ModuleConfig.xml; return the step/group/option tree.

    Args:
        params["archive_path"]: path to extracted FOMOD root (must contain fomod/ subdirectory).

    Returns:
        {
          "fomod_name": str,
          "fomod_version": str | None,
          "pages": [
            {
              "name": str,
              "groups": [
                {"name": str, "type": str, "options": [
                  {"name": str, "description": str, "image": str | None, "type": str}
                ]}
              ]
            }
          ]
        }

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

    pages = []
    for page in getattr(root, "pages", []) or []:
        groups = []
        for group in page:
            options = []
            for opt in group:
                image = getattr(opt, "image", None)
                options.append({
                    "name": getattr(opt, "name", ""),
                    "description": getattr(opt, "description", "") or "",
                    "image": str(image) if image else None,
                    "type": _option_type_name(opt),
                })
            groups.append({
                "name": getattr(group, "name", ""),
                "type": _group_type_name(group),
                "options": options,
            })
        pages.append({"name": getattr(page, "name", ""), "groups": groups})

    version = getattr(root, "version", None)
    return {
        "fomod_name": getattr(root, "name", "") or "",
        "fomod_version": str(version) if version else None,
        "pages": pages,
    }


def fomod_resolve_files(params: dict) -> dict:
    """Apply user choices to a FOMOD installer and return the resolved file mapping.

    pyfomod Installer is wizard-style: next() starts/advances pages, files() at end.
    We walk pages via next(), matching user choices to InstallerOption objects.

    Args:
        params["archive_path"]: path to extracted FOMOD root
        params["choices"]: list of {page_name, selected_options: [{group_name, option_name}]}

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

    installer = pyfomod.Installer(root, path=str(archive_path))
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
