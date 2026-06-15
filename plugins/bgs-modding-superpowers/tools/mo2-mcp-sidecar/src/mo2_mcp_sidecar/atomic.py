"""Atomic file write helpers.

Pattern: write to .tmp-<random> sibling -> fsync -> os.replace.
os.replace is atomic on NTFS + POSIX. Used by sidecar and (later) S1a broker
for meta.ini writes per oracle traps S3.2 and S6.2.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to path atomically via temp file + os.replace.

    Pattern (NTFS + POSIX safe):
    1. mkdir parent if needed
    2. write to a sibling .tmp-XXXX file (same dir for atomic rename)
    3. fsync
    4. os.replace(tmp, path) - atomic on both platforms

    On exception, the temp file is cleaned up best-effort and the exception re-raised.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".tmp-",
        suffix=path.suffix,
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Binary variant of atomic_write_text."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".tmp-",
        suffix=path.suffix,
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@contextmanager
def atomic_write_handle(path: Path, encoding: str = "utf-8") -> Iterator[TextIO]:
    """Context manager for streaming writes.

    Usage:
        with atomic_write_handle(Path("foo.txt")) as f:
            f.write("line 1\\n")
            f.write("line 2\\n")
        # File is atomically renamed into place on exit (or cleaned up on exception)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".tmp-",
        suffix=path.suffix,
    )
    f = os.fdopen(fd, "w", encoding=encoding)
    try:
        yield f
        f.flush()
        os.fsync(f.fileno())
        f.close()
        os.replace(tmp_path, path)
    except Exception:
        try:
            f.close()
        except Exception:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
