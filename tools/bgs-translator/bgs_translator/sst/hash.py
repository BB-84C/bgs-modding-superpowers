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
    """Strip the master-index high byte from a 32-bit FormID.

    Mirrors xTranslator's single-arg ``sanitizeFormID(formID)`` (cf.
    ``TESVT_typedef.pas:472``, ``TESVT_FastSearch.pas:494``). The two-arg
    Pascal overload accepts an optional replacement byte; we expose only the
    common single-arg form because the SST hashing path always uses it.
    """
    return formid & 0x00FFFFFF


def string_hash(s: str) -> int:
    """Compute xTranslator's ``StringHash`` (FNV-1a 32-bit, low-byte iteration)."""
    h = FNV_OFFSET_BASIS
    for ch in s:
        h = ((h ^ (ord(ch) & 0xFF)) * FNV_PRIME) & _MASK32
    return h


def format_no_edid_key(formid: int) -> str:
    """Format the bracketed sanitized-FormID key used when no EditorID exists.

    xTranslator builds the key with Delphi ``format('[%.8x]', [...])``, which
    emits lowercase 8-digit zero-padded hex; we reproduce that with Python's
    ``{:08x}``.
    """
    return f"[{sanitize_formid(formid):08x}]"


def compute_rhash(editor_id: str | None, formid: int) -> int:
    """Compute the SST entry ``rHash`` per the PRD §1.4 / typedef §471 rule.

    - With an EditorID: ``stringHash(editorID)``
    - Without:          ``stringHash('[' + lowercase 8-hex sanitized FormID + ']')``
    """
    if editor_id:
        return string_hash(editor_id)
    return string_hash(format_no_edid_key(formid))
