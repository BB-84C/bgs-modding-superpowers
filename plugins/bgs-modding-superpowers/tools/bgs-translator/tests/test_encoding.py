"""Tests for plugin string decoding fallback chains."""

from __future__ import annotations

import pytest


def test_decode_utf8_first() -> None:
    from bgs_translator.parsers.encoding import decode_with_chain

    decoded, encoding = decode_with_chain(b"hello", ["utf-8", "cp1252"])

    assert decoded == "hello"
    assert encoding == "utf-8"


def test_decode_cp1252_fallback() -> None:
    from bgs_translator.parsers.encoding import decode_with_chain

    decoded, encoding = decode_with_chain(b"\xe9", ["utf-8", "cp1252"])

    assert decoded == "é"
    assert encoding == "cp1252"


def test_all_fail() -> None:
    from bgs_translator.parsers.encoding import decode_with_chain

    with pytest.raises(UnicodeDecodeError, match="ascii"):
        decode_with_chain(b"\xff", ["ascii"])
