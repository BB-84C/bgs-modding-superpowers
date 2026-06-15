"""Security tests for archive path traversal handling."""
from __future__ import annotations

import zipfile

import pytest

from mo2_mcp_sidecar import archive


def test_extract_rejects_parent_traversal_and_leaves_dest_empty(tmp_path):
    archive_path = tmp_path / "evil.zip"
    dest = tmp_path / "staging"
    dest.mkdir()
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("safe.txt", b"should-not-land")
        zf.writestr("../../escape.txt", b"pwned")

    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert list(dest.rglob("*")) == []
    assert not (tmp_path / "escape.txt").exists()


def test_extract_rejects_windows_absolute_path(tmp_path):
    archive_path = tmp_path / "evil.zip"
    dest = tmp_path / "staging"
    dest.mkdir()
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr(r"C:\Windows\evil.txt", b"pwned")

    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert list(dest.rglob("*")) == []


def test_safe_member_rejects_nul_byte(tmp_path):
    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive._validate_safe_member("bad\x00evil.txt", tmp_path)


def test_extract_accepts_legitimate_nested_path(tmp_path):
    archive_path = tmp_path / "safe.zip"
    dest = tmp_path / "staging"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("subdir/file.txt", b"safe")

    result = archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert result["files"] == ["subdir/file.txt"]
    assert (dest / "subdir" / "file.txt").read_bytes() == b"safe"
