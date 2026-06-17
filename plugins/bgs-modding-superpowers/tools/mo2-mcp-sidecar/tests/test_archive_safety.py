"""Security tests for archive path traversal handling."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mo2_mcp_sidecar import archive

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_ZIPSLIP_FIXTURE = _FIXTURES_DIR / "test-zipslip.zip"


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


def test_non_fomod_install_extracts_all_members(tmp_path):
    archive_path = tmp_path / "plain-mod.zip"
    dest = tmp_path / "staging"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("data/file1.txt", b"payload-1")
        zf.writestr("data/file2.txt", b"payload-2")

    result = archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert result["files"] == ["data/file1.txt", "data/file2.txt"]
    assert (dest / "data" / "file1.txt").read_bytes() == b"payload-1"
    assert (dest / "data" / "file2.txt").read_bytes() == b"payload-2"


def test_non_fomod_install_doesnt_look_for_fomod_subdir(tmp_path):
    archive_path = tmp_path / "plain-mod-with-bad-member.zip"
    dest = tmp_path / "staging"
    dest.mkdir()
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("data/file1.txt", b"payload-1")
        zf.writestr("../escape.txt", b"bad")

    with pytest.raises(ValueError) as excinfo:
        archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert "path_traversal_blocked" in str(excinfo.value)
    assert "fomod" not in str(excinfo.value).lower()


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


# --- C.1.3 carryforward: zip-slip fixture coverage --------------------------
#
# The committed fixture at tests/fixtures/test-zipslip.zip contains 4 raw entry
# names representing real attack shapes a malicious mod archive could carry:
#
#     legit/file.txt              -> legitimate control (must pass alone)
#     ../escape.txt               -> relative-up traversal
#     C:/evil/bad.txt             -> absolute Windows path
#     subdir/../../escape.txt     -> embedded traversal inside a nested path
#
# Each per-member test calls ``_validate_safe_member`` directly so the rejection
# is attributed to the specific attack shape, not to whichever entry happened
# to be iterated first by ``archive_extract_all``.  The final integration test
# confirms the whole fixture is rejected end-to-end and that nothing lands in
# the staging directory.


def _fixture_member_names() -> list[str]:
    with zipfile.ZipFile(_ZIPSLIP_FIXTURE) as zf:
        return zf.namelist()


def test_zipslip_fixture_is_present_and_has_expected_members():
    """Guard against accidental fixture drift (raw entry names must survive)."""
    assert _ZIPSLIP_FIXTURE.is_file(), f"fixture missing: {_ZIPSLIP_FIXTURE}"
    names = _fixture_member_names()
    assert "legit/file.txt" in names
    assert "../escape.txt" in names
    assert "C:/evil/bad.txt" in names
    assert "subdir/../../escape.txt" in names


def test_zipslip_relative_up_rejected(tmp_path):
    names = _fixture_member_names()
    assert "../escape.txt" in names
    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive._validate_safe_member("../escape.txt", tmp_path)


def test_zipslip_absolute_path_rejected(tmp_path):
    names = _fixture_member_names()
    assert "C:/evil/bad.txt" in names
    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive._validate_safe_member("C:/evil/bad.txt", tmp_path)


def test_zipslip_embedded_traversal_rejected(tmp_path):
    names = _fixture_member_names()
    assert "subdir/../../escape.txt" in names
    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive._validate_safe_member("subdir/../../escape.txt", tmp_path)


def test_zipslip_legit_member_alone_passes(tmp_path):
    """Positive control: the benign member from the same fixture extracts fine."""
    names = _fixture_member_names()
    assert "legit/file.txt" in names
    resolved = archive._validate_safe_member("legit/file.txt", tmp_path)
    assert resolved == (tmp_path / "legit" / "file.txt").resolve()


def test_zipslip_fixture_full_extraction_rejected_and_dest_left_empty(tmp_path):
    """End-to-end: archive_extract_all on the fixture must refuse and not write."""
    dest = tmp_path / "staging"
    dest.mkdir()
    with pytest.raises(ValueError, match="path_traversal_blocked"):
        archive.archive_extract_all(
            {"archive_path": str(_ZIPSLIP_FIXTURE), "dest": str(dest)}
        )
    assert list(dest.rglob("*")) == []
    # Defense-in-depth: no sibling escape artifact landed next to dest either.
    assert not (tmp_path / "escape.txt").exists()


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
