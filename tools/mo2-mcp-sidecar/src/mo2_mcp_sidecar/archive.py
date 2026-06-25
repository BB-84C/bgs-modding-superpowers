"""Archive extraction JSON-RPC method (.zip / .7z / .rar) - PLAN-PATCH P-B6.

Used by mo2_install's plan step to stage archive contents into
<MO2_Root>/.mo2-mcp/staging/<install_id>/ before computing conflict preview.

BUG-14 BUG-C fix (issue #14): py7zr's ``SevenZipFile`` only understands the
7z container format and raises ``Bad7zFile: not a 7z file`` on .rar input.
The .rar branch shells out to ``7z.exe`` (the 7-Zip CLI), which handles
RAR natively. Nexus carries a long tail of .rar uploads (older mods, e.g.
Starfield Extended - Craftable Quality v4.1 #5721 ships as .rar) and the
prior code path made ``mo2_install`` unusable for them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any

from .envelope import register_method

try:
    import py7zr
    _PY7ZR_AVAILABLE = True
except ImportError:
    _PY7ZR_AVAILABLE = False


# Well-known Windows 7-Zip install paths used as a fallback when neither
# BGS_SEVENZIP_PATH nor a PATH lookup turns up the binary.
_WIN_7Z_FALLBACK_PATHS = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
)


def _find_7z_exe() -> str | None:
    """Locate a usable 7-Zip CLI for shell-out extraction.

    Precedence:
      1. ``$BGS_SEVENZIP_PATH`` (explicit override; agent installs / CI)
      2. ``shutil.which("7z")`` / ``shutil.which("7z.exe")`` (PATH lookup)
      3. Well-known Windows install paths

    Returns the resolved binary path or ``None`` if 7-Zip is not findable.
    Callers raise an actionable error pointing at the install URL.
    """
    env_path = os.environ.get("BGS_SEVENZIP_PATH")
    if env_path and Path(env_path).is_file():
        return env_path
    for name in ("7z", "7z.exe"):
        which = shutil.which(name)
        if which:
            return which
    for candidate in _WIN_7Z_FALLBACK_PATHS:
        if Path(candidate).is_file():
            return candidate
    return None


def _list_via_7z_exe(seven_z: str, archive_path: Path) -> list[str]:
    """Enumerate archive members via ``7z l -slt`` so they can be pre-validated.

    Defense-in-depth: even though 7-Zip itself sanitizes against absolute
    paths and ``..`` traversal in modern versions, we still pre-list and
    run each member through :func:`_validate_safe_member` so the contract
    matches the .zip / .7z branches above.
    """
    result = subprocess.run(
        [seven_z, "l", "-slt", str(archive_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(no stderr)"
        raise RuntimeError(f"7z_list_failed: exit {result.returncode}: {stderr}")
    members: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("Path = "):
            members.append(line[len("Path = "):])
    # First "Path = " in -slt is the archive itself; skip.
    return members[1:] if members else []


def _extract_via_7z_exe(archive_path: Path, dest: Path) -> list[str]:
    """Extract any archive 7-Zip understands (used for .rar here).

    Validates each member name via :func:`_validate_safe_member` before
    invoking the CLI. After extraction walks ``dest`` to enumerate the
    actually-extracted files (7-Zip emits no JSON listing on stdout, so
    a directory walk is the most portable enumeration path and keeps
    behavior parallel to the .zip / .7z branches).
    """
    seven_z = _find_7z_exe()
    if seven_z is None:
        raise RuntimeError(
            "7z_exe_not_found: set BGS_SEVENZIP_PATH or install 7-Zip from "
            "https://www.7-zip.org/ to enable .rar extraction"
        )

    members = _list_via_7z_exe(seven_z, archive_path)
    for member in members:
        if member:
            _validate_safe_member(member, dest)

    try:
        result = subprocess.run(
            [
                seven_z, "x",
                str(archive_path),
                f"-o{dest}",
                "-y",
                "-bso0",
                "-bsp0",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("7z_exe_timeout: archive extraction exceeded 300s") from exc

    if result.returncode != 0:
        # 7z exit codes: 0=ok, 1=warning, 2=fatal, 7=cmdline, 8=memory, 255=user abort
        stderr = (result.stderr or "").strip() or "(no stderr)"
        raise RuntimeError(f"7z_exe_failed: exit {result.returncode}: {stderr}")

    extracted: list[str] = []
    for path in dest.rglob("*"):
        if path.is_file():
            extracted.append(path.relative_to(dest).as_posix())
    return extracted


def _is_absolute_member(member_name: str) -> bool:
    windows_path = PureWindowsPath(member_name)
    return (
        os.path.isabs(member_name)
        or PurePath(member_name).is_absolute()
        or PurePosixPath(member_name).is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or member_name.startswith(("/", "\\"))
    )


def _validate_safe_member(member_name: str, base_dir: Path) -> Path:
    """Return the resolved target path for a safe archive member.

    Archive member names are attacker-controlled. Reject anything that could
    escape ``base_dir`` before calling a library extractor.
    """
    if not member_name or "\x00" in member_name:
        raise ValueError(f"path_traversal_blocked: {member_name!r}")

    windows_path = PureWindowsPath(member_name)
    if _is_absolute_member(member_name):
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


def _safe_7z_targets(member_infos: list[Any], base_dir: Path) -> list[str]:
    """Return py7zr target names that are safe to extract under ``base_dir``.

    py7zr archives created with ``writeall(<absolute source dir>)`` may contain
    a directory-only member for the absolute build root, followed by the real
    relative payload entries.  The absolute root marker is not payload; extracting
    it would either fail py7zr's own sanitizer or attempt to leave the staging
    root.  Ignore only absolute directory markers, while continuing to reject any
    absolute file member or relative traversal member.
    """
    targets: list[str] = []
    for info in member_infos:
        name = str(getattr(info, "filename", info))
        is_directory = bool(getattr(info, "is_directory", False))
        if _is_absolute_member(name):
            if is_directory:
                continue
            raise ValueError(f"path_traversal_blocked: {name!r}")
        _validate_safe_member(name, base_dir)
        targets.append(name)
    return targets


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
    elif suffix == ".7z":
        if not _PY7ZR_AVAILABLE:
            raise RuntimeError("py7zr_not_available")
        with py7zr.SevenZipFile(archive_path) as z:
            extracted = _safe_7z_targets(list(z.list()), dest)
            if extracted:
                z.extract(path=str(dest), targets=extracted)
        fmt = "7z"
    elif suffix == ".rar":
        # BUG-14 BUG-C (issue #14): py7zr does NOT support RAR; routing it
        # through SevenZipFile produced ``Bad7zFile: not a 7z file`` and
        # made every .rar Nexus archive uninstallable via mo2_install.
        # Shell out to 7z.exe which understands the format natively.
        extracted = _extract_via_7z_exe(archive_path, dest)
        fmt = "rar"
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
