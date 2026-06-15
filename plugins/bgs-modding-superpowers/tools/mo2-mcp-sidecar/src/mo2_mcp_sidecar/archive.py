"""Archive extraction JSON-RPC method (.zip / .7z / .rar) - PLAN-PATCH P-B6.

Used by mo2_install's plan step to stage archive contents into
<MO2_Root>/.mo2-mcp/staging/<install_id>/ before computing conflict preview.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any

from .envelope import register_method

try:
    import py7zr
    _PY7ZR_AVAILABLE = True
except ImportError:
    _PY7ZR_AVAILABLE = False


def _validate_safe_member(member_name: str, base_dir: Path) -> Path:
    """Return the resolved target path for a safe archive member.

    Archive member names are attacker-controlled. Reject anything that could
    escape ``base_dir`` before calling a library extractor.
    """
    if not member_name or "\x00" in member_name:
        raise ValueError(f"path_traversal_blocked: {member_name!r}")

    windows_path = PureWindowsPath(member_name)
    if (
        os.path.isabs(member_name)
        or PurePath(member_name).is_absolute()
        or PurePosixPath(member_name).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or member_name.startswith(("/", "\\"))
    ):
        raise ValueError(f"path_traversal_blocked: {member_name!r}")

    if ".." in PurePath(member_name).parts or ".." in PurePosixPath(member_name).parts:
        raise ValueError(f"path_traversal_blocked: {member_name!r}")
    if ".." in windows_path.parts:
        raise ValueError(f"path_traversal_blocked: {member_name!r}")

    base_resolved = base_dir.resolve()
    resolved = (base_dir / member_name).resolve()
    if not resolved.is_relative_to(base_resolved):
        raise ValueError(f"path_traversal_blocked: {member_name!r}")
    return resolved


def archive_extract_all(params: dict[str, Any]) -> dict[str, Any]:
    """Extract entire archive to dest. Supports .zip natively; .7z/.rar via py7zr.

    Args:
        params["archive_path"]: absolute path to archive
        params["dest"]: absolute path to destination directory (created if missing)

    Returns:
        {"files": [str], "file_count": int, "dest": str, "format": str}

    Raises:
        FileNotFoundError if archive missing
        RuntimeError("unsupported_archive_format: <ext>") for unknown extensions
        RuntimeError("py7zr_not_available") if .7z/.rar but py7zr missing
    """
    archive_path = Path(params["archive_path"])
    dest = Path(params["dest"])
    if not archive_path.exists():
        raise FileNotFoundError(f"archive not found: {archive_path}")

    dest.mkdir(parents=True, exist_ok=True)
    suffix = archive_path.suffix.lower()
    extracted: list[str] = []

    if suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            extracted = zf.namelist()
            for name in extracted:
                _validate_safe_member(name, dest)
            zf.extractall(dest)
        fmt = "zip"
    elif suffix in (".7z", ".rar"):
        if not _PY7ZR_AVAILABLE:
            raise RuntimeError("py7zr_not_available")
        with py7zr.SevenZipFile(archive_path) as z:
            extracted = list(z.getnames())
            for name in extracted:
                _validate_safe_member(name, dest)
            z.extractall(path=str(dest))
        fmt = "7z" if suffix == ".7z" else "rar"
    else:
        raise RuntimeError(f"unsupported_archive_format: {suffix}")

    return {
        "files": extracted,
        "file_count": len(extracted),
        "dest": str(dest),
        "format": fmt,
    }


def register() -> None:
    register_method("archive.extract_all", archive_extract_all)
