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


# BUG-14 BUG-C (issue #14): .rar must NOT route through py7zr (Bad7zFile
# error) and must succeed when 7z.exe is available on PATH / fallback paths
# / via BGS_SEVENZIP_PATH override.
class TestRarSupport:
    def test_find_7z_exe_honors_env_override(self, tmp_path, monkeypatch):
        fake = tmp_path / "fake-7z.exe"
        fake.write_text("not really a binary")  # only needs to exist
        monkeypatch.setenv("BGS_SEVENZIP_PATH", str(fake))
        assert archive._find_7z_exe() == str(fake)

    def test_find_7z_exe_ignores_nonexistent_override(self, monkeypatch):
        monkeypatch.setenv("BGS_SEVENZIP_PATH", "/path/that/does/not/exist/7z.exe")
        # Should fall through to PATH lookup / fallback paths; we don't
        # assert a specific result here because it depends on the host's
        # 7-Zip install. We just assert it doesn't raise.
        result = archive._find_7z_exe()
        assert result is None or Path(result).is_file()

    def test_extract_rar_raises_clear_error_when_7z_exe_missing(self, tmp_path, monkeypatch):
        # Force _find_7z_exe to return None.
        monkeypatch.setattr(archive, "_find_7z_exe", lambda: None)
        # Create a fake .rar file (we never actually try to read it because
        # _find_7z_exe is mocked to return None before the shell-out).
        rar = tmp_path / "fake.rar"
        rar.write_bytes(b"Rar!\x1a\x07\x00")  # RAR magic, content irrelevant
        with pytest.raises(RuntimeError, match="7z_exe_not_found"):
            archive.archive_extract_all({
                "archive_path": str(rar),
                "dest": str(tmp_path / "out"),
            })

    def test_extract_rar_routes_through_7z_exe_not_py7zr(self, tmp_path, monkeypatch):
        """Asserts the .rar branch invokes 7z.exe and bypasses py7zr.

        Without the fix, .rar fell into the (.7z, .rar) branch and py7zr
        raised Bad7zFile. Mock _find_7z_exe + subprocess.run + the directory
        walk to prove the routing without requiring a real RAR fixture.
        """
        seven_z_path = "/fake/7z.exe"
        monkeypatch.setattr(archive, "_find_7z_exe", lambda: seven_z_path)

        calls: list[tuple] = []

        def _fake_list(seven_z, archive_path):
            calls.append(("list", seven_z, str(archive_path)))
            return ["only.txt"]

        monkeypatch.setattr(archive, "_list_via_7z_exe", _fake_list)

        class _FakeResult:
            returncode = 0
            stderr = ""
            stdout = ""

        def _fake_run(cmd, **kwargs):
            calls.append(("run", tuple(cmd)))
            # Simulate extraction by creating the destination file. The
            # -o<dest> argument is the only one starting with "-o".
            dest_arg = next(a for a in cmd if a.startswith("-o"))
            dest = Path(dest_arg[2:])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "only.txt").write_text("extracted from rar")
            return _FakeResult()

        monkeypatch.setattr(archive.subprocess, "run", _fake_run)

        rar = tmp_path / "fake.rar"
        rar.write_bytes(b"Rar!\x1a\x07\x00")
        dest = tmp_path / "out"
        result = archive.archive_extract_all({
            "archive_path": str(rar),
            "dest": str(dest),
        })

        assert result["format"] == "rar"
        assert "only.txt" in result["files"]
        assert (dest / "only.txt").read_text() == "extracted from rar"
        # Prove the 7z.exe path was actually taken.
        assert any(c[0] == "list" for c in calls), f"list step missing: {calls}"
        assert any(c[0] == "run" and seven_z_path in c[1] for c in calls), f"7z.exe invocation missing: {calls}"

    def test_extract_rar_propagates_7z_exit_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(archive, "_find_7z_exe", lambda: "/fake/7z.exe")
        monkeypatch.setattr(archive, "_list_via_7z_exe", lambda _s, _a: [])

        class _FakeResult:
            returncode = 2  # 7z fatal exit
            stderr = "Cannot open the file as archive"
            stdout = ""

        def _fake_run(cmd, **kwargs):
            return _FakeResult()

        monkeypatch.setattr(archive.subprocess, "run", _fake_run)
        rar = tmp_path / "bad.rar"
        rar.write_bytes(b"Rar!\x1a\x07\x00")
        with pytest.raises(RuntimeError, match="7z_exe_failed: exit 2"):
            archive.archive_extract_all({
                "archive_path": str(rar),
                "dest": str(tmp_path / "out"),
            })
