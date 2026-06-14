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

    try:
        root = pyfomod.parse(str(archive_path))
    except Exception as exc:
        raise RuntimeError(f"not_a_fomod: {exc}")

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


def register() -> None:
    register_method("fomod.parse_choices", fomod_parse_choices)
    # Task 28 will add fomod.resolve_files here
