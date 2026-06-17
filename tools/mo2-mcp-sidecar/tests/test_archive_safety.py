"""Security tests for archive path traversal handling."""
from __future__ import annotations

import zipfile

import pytest

from mo2_mcp_sidecar import archive


class _SevenZipInfo:
    def __init__(self, filename: str, is_directory: bool) -> None:
        self.filename = filename
        self.is_directory = is_directory


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


def test_safe_member_accepts_underscore_prefixed_fixture_paths(tmp_path):
    assert archive._validate_safe_member("_build/simple/file.txt", tmp_path) == (
        tmp_path / "_build" / "simple" / "file.txt"
    ).resolve()
    assert archive._validate_safe_member("_build/fomodsrc/fomod/info.xml", tmp_path) == (
        tmp_path / "_build" / "fomodsrc" / "fomod" / "info.xml"
    ).resolve()


def test_safe_member_rejects_nested_parent_traversal(tmp_path):
    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive._validate_safe_member("subdir/../../escape.txt", tmp_path)


def test_safe_7z_targets_ignore_absolute_build_root_directory_marker(tmp_path):
    infos = [
        _SevenZipInfo(
            "D:/awesome-bgs-mod-master/.opencode/artifacts/mo2-mcp/acceptance/fixtures/_build/simple",
            is_directory=True,
        ),
        _SevenZipInfo("textures", is_directory=True),
        _SevenZipInfo("textures/e2e/simple.txt", is_directory=False),
    ]

    assert archive._safe_7z_targets(infos, tmp_path) == ["textures", "textures/e2e/simple.txt"]


def test_safe_7z_targets_reject_absolute_file_members(tmp_path):
    infos = [_SevenZipInfo("D:/evil/bad.txt", is_directory=False)]

    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive._safe_7z_targets(infos, tmp_path)


@pytest.mark.skipif(not archive._PY7ZR_AVAILABLE, reason="py7zr not installed")
def test_extract_7z_ignores_py7zr_absolute_build_root_marker(tmp_path):
    """py7zr writeall() can include an absolute source-root dir marker.

    The acceptance fixtures contain such a directory-only marker for their
    ``.../fixtures/_build/...`` source root, followed by legitimate relative
    members.  That marker must not be treated as archive payload, and it must
    not block extracting the safe relative files.
    """
    import py7zr

    source_root = tmp_path / "acceptance" / "fixtures" / "_build" / "simple"
    (source_root / "textures" / "e2e").mkdir(parents=True)
    (source_root / "textures" / "e2e" / "simple.txt").write_text("payload", encoding="utf-8")
    archive_path = tmp_path / "test-simple.7z"
    with py7zr.SevenZipFile(archive_path, "w") as z:
        z.write(
            source_root,
            arcname=(
                "D:/awesome-bgs-mod-master/.opencode/artifacts/mo2-mcp"
                "/acceptance/fixtures/_build/simple"
            ),
        )
        z.write(source_root / "textures" / "e2e" / "simple.txt", arcname="textures/e2e/simple.txt")

    dest = tmp_path / "staging"
    result = archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert "textures/e2e/simple.txt" in result["files"]
    assert (dest / "textures" / "e2e" / "simple.txt").read_text(encoding="utf-8") == "payload"
    assert not (dest / str(source_root.drive).rstrip(":")).exists()
