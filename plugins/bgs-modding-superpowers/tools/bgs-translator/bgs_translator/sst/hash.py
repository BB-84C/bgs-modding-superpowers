"""xTranslator's ``stringHash`` and ``sanitizeFormID`` helpers.

These two functions decide whether our SST entry's ``rHash`` field matches
xTranslator's internal lookup. Bit-exact reproduction is required: the GUI
keys translation memory on this hash.

Provenance: ``TESVT_Const.pas:2452`` (StringHash) and ``TESVT_typedef.pas:471``
(the rHash normalization branch) in https://github.com/MGuffin/xTranslator,
fetched 2026-06-07. Pascal source::

    function StringHash(const str: String): cardinal;
    const
      FNV_offset_basis = 2166136261;
      FNV_prime = 16777619;
    begin
      Result := FNV_offset_basis;
      for i := 1 to length(str) do
        Result := (Result xor byte(str[i])) * FNV_prime;
    end;

In Delphi a ``string`` is a ``UnicodeString`` (UTF-16). ``byte(str[i])``
truncates each WideChar to its low byte. For EditorIDs and the
``'[xxxxxxxx]'`` fallback (both pure ASCII) the low byte is the ASCII byte,
so iterating Python str codepoints masked with ``0xFF`` reproduces the
result exactly.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "FNV_OFFSET_BASIS",
    "FNV_PRIME",
    "compute_rhash",
    "format_no_edid_key",
    "sanitize_formid",
    "string_hash",
]


FNV_OFFSET_BASIS: Final[int] = 0x811C9DC5  # 2166136261
FNV_PRIME: Final[int] = 0x01000193  # 16777619
_MASK32: Final[int] = 0xFFFFFFFF


def sanitize_formid(formid: int) -> int:
    """Return xTranslator's default ``sanitizeFormID(formID)`` value.

    xTranslator does not simply drop the load-order byte when building SST
    hashes. Its default ``bS`` value is ``$01``, so normal master FormIDs are
    normalized to ``01xxxxxx``. The exact value matters for no-EDID records
    such as ``INFO:NAM1`` because V4 SST import compares this rHash before it
    compares record/field/index metadata.
    """

    value = int(formid) & _MASK32
    high = (value >> 24) & 0xFF
    if high == 0:
        return value
    if high == 0xFE:
        if ((value >> 12) & 0xFF) == 0:
            return value
        return (value & ~(0xFFF << 12)) | (0x01 << 12)
    if high == 0xFD:
        if ((value >> 16) & 0xFF) == 0:
            return value
        return (value & ~(0xFF << 16)) | (0x01 << 16)
    return (value & 0x00FFFFFF) | (0x01 << 24)


def string_hash(s: str) -> int:
    """Compute xTranslator's ``StringHash`` (FNV-1a 32-bit, low-byte iteration)."""
    h = FNV_OFFSET_BASIS
    for ch in s:
        h = ((h ^ (ord(ch) & 0xFF)) * FNV_PRIME) & _MASK32
    return h


def format_no_edid_key(formid: int) -> str:
    """Format the bracketed xTranslator FormID key used without an EditorID.

    xTranslator builds the key with Delphi ``format('[%.8x]', [...])``. Delphi
    emits uppercase A-F for this format, and ``stringHash`` is case-sensitive.
    """
    return f"[{sanitize_formid(formid):08X}]"


def compute_rhash(editor_id: str | None, formid: int) -> int:
    """Compute the SST entry ``rHash`` per the PRD §1.4 / typedef §471 rule.

    - With an EditorID: ``stringHash(editorID)``
    - Without:          ``stringHash('[' + uppercase 8-hex sanitized FormID + ']')``
    """
    if editor_id:
        return string_hash(editor_id)
    return string_hash(format_no_edid_key(formid))
