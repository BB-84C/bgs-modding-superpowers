"""Unit tests for archive.extract_all."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mo2_mcp_sidecar import archive
from mo2_mcp_sidecar.envelope import _METHODS


@pytest.fixture(autouse=True)
def clear_methods():
    _METHODS.clear()
    yield
    _METHODS.clear()


def _make_zip(tmp_path: Path) -> Path:
    src = tmp_path / "src.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("hello.txt", "hello")
        zf.writestr("nested/deep.txt", "deep content")
    return src


def test_extract_all_zip_creates_files(tmp_path):
    archive_path = _make_zip(tmp_path)
    dest = tmp_path / "out"

    result = archive.archive_extract_all({
        "archive_path": str(archive_path),
        "dest": str(dest),
    })

    assert result["format"] == "zip"
    assert result["file_count"] == 2
    assert (dest / "hello.txt").read_text() == "hello"
    assert (dest / "nested" / "deep.txt").read_text() == "deep content"


def test_extract_all_creates_dest_dir(tmp_path):
    archive_path = _make_zip(tmp_path)
    dest = tmp_path / "newly" / "created" / "dest"

    archive.archive_extract_all({"archive_path": str(archive_path), "dest": str(dest)})

    assert dest.exists()


def test_extract_all_missing_archive_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        archive.archive_extract_all({"archive_path": "/nope.zip", "dest": str(tmp_path)})


def test_extract_all_unknown_format_raises(tmp_path):
    fake = tmp_path / "fake.tar.gz"
    fake.write_bytes(b"not a real archive")

    with pytest.raises(RuntimeError, match="unsupported_archive_format"):
        archive.archive_extract_all({"archive_path": str(fake), "dest": str(tmp_path / "out")})


def test_register_wires_archive_extract_all():
    archive.register()
    assert "archive.extract_all" in _METHODS


@pytest.mark.skipif(not archive._PY7ZR_AVAILABLE, reason="py7zr not installed")
def test_extract_all_7z_format(tmp_path):
    """If py7zr available, .7z extracts cleanly."""
    import py7zr
    src = tmp_path / "src.7z"
    with py7zr.SevenZipFile(src, "w") as z:
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        (scratch / "inside.txt").write_text("inside-7z")
        z.write(scratch / "inside.txt", arcname="inside.txt")

    dest = tmp_path / "out_7z"
    result = archive.archive_extract_all({"archive_path": str(src), "dest": str(dest)})

    assert result["format"] == "7z"
    assert (dest / "inside.txt").read_text() == "inside-7z"
