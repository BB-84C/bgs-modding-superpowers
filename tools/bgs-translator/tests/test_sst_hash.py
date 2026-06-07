"""Tests for ``stringHash``, ``sanitize_formid``, and ``compute_rhash``."""

from __future__ import annotations

from bgs_translator.sst.hash import (
    FNV_OFFSET_BASIS,
    FNV_PRIME,
    compute_rhash,
    format_no_edid_key,
    sanitize_formid,
    string_hash,
)


def test_sanitize_formid_strips_master_byte() -> None:
    assert sanitize_formid(0x02000800) == 0x00000800
    assert sanitize_formid(0xFF123456) == 0x00123456
    assert sanitize_formid(0x00000000) == 0x00000000
    # Idempotent
    assert sanitize_formid(sanitize_formid(0x02000800)) == 0x00000800


def test_string_hash_empty_is_offset_basis() -> None:
    # FNV-1a definition: empty string returns the offset basis unchanged.
    assert string_hash("") == FNV_OFFSET_BASIS


def test_string_hash_single_byte_matches_fnv1a_definition() -> None:
    # Single 'a' = 0x61. Expected = (offset XOR 0x61) * prime mod 2^32.
    expected = ((FNV_OFFSET_BASIS ^ 0x61) * FNV_PRIME) & 0xFFFFFFFF
    assert string_hash("a") == expected


def test_string_hash_known_vector_foobar() -> None:
    # Standard FNV-1a 32-bit test vector for "foobar" = 0xBF9CF968.
    # https://datatracker.ietf.org/doc/html/draft-eastlake-fnv (Appendix C).
    assert string_hash("foobar") == 0xBF9CF968


def test_string_hash_known_vector_hello() -> None:
    # Hand-computed FNV-1a 32-bit for "hello":
    #   bytes = 68 65 6c 6c 6f
    #   h = 0x811C9DC5
    #   for each b: h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    # Verified via independent reference implementation.
    assert string_hash("hello") == 0x4F9F2CAB


def test_string_hash_takes_low_byte_of_codepoint() -> None:
    # Pascal: ``byte(str[i])`` truncates each WideChar to its low byte. We
    # mirror that by masking ``ord(ch) & 0xFF``.
    # '\u0161' has codepoint 0x161; low byte = 0x61 = 'a'. Hashes must match.
    assert string_hash("\u0161") == string_hash("a")


def test_format_no_edid_key_uses_lowercase_eight_hex() -> None:
    assert format_no_edid_key(0) == "[00000000]"
    assert format_no_edid_key(0x0000ABCD) == "[0000abcd]"
    # Master byte is stripped before formatting.
    assert format_no_edid_key(0x02000800) == "[00000800]"


def test_compute_rhash_with_edid_uses_edid() -> None:
    assert compute_rhash("MyEditorID", 0x02000800) == string_hash("MyEditorID")


def test_compute_rhash_without_edid_uses_bracketed_sanitized_formid() -> None:
    rhash = compute_rhash(None, 0x02000800)
    assert rhash == string_hash("[00000800]")


def test_compute_rhash_empty_edid_falls_back_to_bracketed_form() -> None:
    # An empty EditorID is semantically "no EditorID".
    assert compute_rhash("", 0x00000000) == string_hash("[00000000]")


def test_string_hash_returns_uint32() -> None:
    # Long input — make sure the modular reduction stays within 32-bit.
    h = string_hash("X" * 4096)
    assert 0 <= h <= 0xFFFFFFFF


def test_srb_fixture_no_edid_record_matches_observed_rhash() -> None:
    # In the spike fixture ``srb_showreadbooks_en_zhhans.sst`` the TES4:CNAM
    # entry (header record, no EditorID, formID=0) has rHash 0xEF7C96E5.
    # This is the FNV-1a hash of "[00000000]".
    assert compute_rhash(None, 0x00000000) == 0xEF7C96E5
