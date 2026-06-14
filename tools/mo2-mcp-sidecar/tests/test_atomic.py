"""Unit tests for atomic write helpers."""
from __future__ import annotations

import os

import pytest

from mo2_mcp_sidecar.atomic import atomic_write_bytes, atomic_write_handle, atomic_write_text


def test_atomic_write_text_creates_file_with_content(tmp_path):
    target = tmp_path / "subdir" / "out.txt"  # parent doesn't exist yet

    atomic_write_text(target, "hello world\n")

    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_atomic_write_text_overwrites_existing(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_text_preserves_old_on_exception(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"
    target.write_text("original", encoding="utf-8")

    # Force os.replace to fail mid-write
    def _boom(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError, match="simulated"):
        atomic_write_text(target, "new content that should not land")

    # Old content preserved
    assert target.read_text(encoding="utf-8") == "original"
    # Temp file cleaned up
    siblings = list(tmp_path.glob(".tmp-*"))
    assert siblings == [], f"leftover temp files: {siblings}"


def test_atomic_write_text_no_leftover_tmp_on_success(tmp_path):
    target = tmp_path / "out.txt"
    atomic_write_text(target, "data")
    siblings = list(tmp_path.glob(".tmp-*"))
    assert siblings == []


def test_atomic_write_bytes_creates_file(tmp_path):
    target = tmp_path / "out.bin"
    atomic_write_bytes(target, b"\x00\x01\x02\xff")
    assert target.read_bytes() == b"\x00\x01\x02\xff"


def test_atomic_write_handle_streams_content(tmp_path):
    target = tmp_path / "stream.txt"

    with atomic_write_handle(target) as f:
        f.write("line 1\n")
        f.write("line 2\n")

    assert target.read_text(encoding="utf-8") == "line 1\nline 2\n"


def test_atomic_write_handle_cleans_up_on_exception(tmp_path):
    target = tmp_path / "stream.txt"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(ValueError, match="user error"):
        with atomic_write_handle(target) as f:
            f.write("partial")
            raise ValueError("user error")

    # Original preserved
    assert target.read_text(encoding="utf-8") == "original"
    siblings = list(tmp_path.glob(".tmp-*"))
    assert siblings == []
