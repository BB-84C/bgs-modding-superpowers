"""Byte-exact writer for xTranslator SST vocab files.

The default emit target is SSU9; SSU8 is supported as a documented downgrade
for older xTranslator installs (it loses the master-list section). Everything
else (SSU2..SSU7) is read-only.

Layout reference (CONFIRMED against ``TESVT_SSTFunc.pas:SaveSSTFile`` and
``TESVT_typedef.pas:rEspPointerLite``):

    SSU9 header:
      [4]  magic                                          = 0x39555353
      [1]  flag byte                                      = 0
      [4]  masterCount : Int32 LE
        per master: [4] byteSize Int32 LE + UTF-16LE bytes
      [4]  colabCount : Int32 LE
        per colab:  [4] colabId Int32 LE
                    [4] byteSize Int32 LE + UTF-16LE bytes
      entries (EOF-terminated; no count field).

    SSU8 downgrade: drop the masterList block; everything else identical.

    Per entry (31 fixed bytes + variable strings):
      [1]  listIndex
      [24] rEspPointerLite = <iI4s4sHHI
      [1]  colabId
      [1]  sParams (1 byte; VALIDATED is stripped)
      [4]  src_size  Int32 LE
      [N]  src       UTF-16LE
      [4]  dst_size  Int32 LE
      [N]  dst       UTF-16LE
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from io import BufferedWriter
from pathlib import Path
from typing import BinaryIO, Final, Literal

from .envelope import magic_for_label
from .status import to_byte

__all__ = [
    "ENTRY_FIXED_SIZE",
    "POINTER_LITE_SIZE",
    "POINTER_LITE_STRUCT",
    "SSTUnit",
    "encode_pointer_lite",
    "write_sst",
]


# ``<iI4s4sHHI`` packs the 24-byte rEspPointerLite:
#   <  little-endian, no padding
#   i  strID         (signed Int32)
#   I  formID        (UInt32 — high byte is master index)
#   4s rName (sig)   (4 ASCII bytes)
#   4s fName (subrec)(4 ASCII bytes)
#   H  index         (UInt16)
#   H  indexMax      (UInt16)
#   I  rHash         (UInt32)
POINTER_LITE_STRUCT: Final[struct.Struct] = struct.Struct("<iI4s4sHHI")
POINTER_LITE_SIZE: Final[int] = POINTER_LITE_STRUCT.size  # 24
assert POINTER_LITE_SIZE == 24, "rEspPointerLite must pack to 24 bytes"

# Per-entry fixed metadata: listIndex(1) + pointer(24) + colabId(1) + sParams(1)
#                         + src_size(4) + dst_size(4) = 35 — but the two
# size prefixes flank the variable strings, so the "fixed-up-to-the-source"
# region documented in the spike is 31 bytes (1+24+1+1+4).
ENTRY_FIXED_SIZE: Final[int] = 31

_VERSION_LABELS: Final[tuple[str, ...]] = ("SSU8", "SSU9")
SSTWriteVersion = Literal["SSU8", "SSU9"]


@dataclass(slots=True)
class SSTUnit:
    """One translatable string ready to land in an SST entry.

    Field semantics match the PRD §1.2 / §1.3 contract. ``rhash`` is *not*
    recomputed by the writer; callers must precompute it through
    :func:`bgs_translator.sst.hash.compute_rhash` so the writer stays a thin
    serializer (separation of concerns from §6 of the SST spec).
    """

    list_index: int
    strid: int
    formid: int  # ORIGINAL formid including master high byte
    signature: str  # 4-char record sig, e.g. "PERK"
    field: str  # 4-char subrec sig, e.g. "EPF2"
    index: int = 0
    index_max: int = 0
    rhash: int = 0
    colab_id: int = 0
    s_params: int = 0
    source: str = ""
    dest: str = ""


def _encode_sig(name: str, *, field_label: str) -> bytes:
    """Encode a 4-char ASCII signature, padding short values with NULs."""
    try:
        raw = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            f"{field_label} signature must be 4 ASCII bytes; got {name!r}"
        ) from exc
    if len(raw) > 4:
        raise ValueError(
            f"{field_label} signature too long ({len(raw)} bytes); got {name!r}"
        )
    if len(raw) < 4:
        raw = raw + (b"\x00" * (4 - len(raw)))
    return raw


def encode_pointer_lite(unit: SSTUnit) -> bytes:
    """Pack the 24-byte rEspPointerLite struct."""
    if not 0 <= unit.list_index <= 0xFF:
        raise ValueError(f"list_index out of byte range: {unit.list_index!r}")
    if not 0 <= unit.index <= 0xFFFF:
        raise ValueError(f"index out of UInt16 range: {unit.index!r}")
    if not 0 <= unit.index_max <= 0xFFFF:
        raise ValueError(f"index_max out of UInt16 range: {unit.index_max!r}")
    if not 0 <= unit.formid <= 0xFFFFFFFF:
        raise ValueError(f"formid out of UInt32 range: {unit.formid!r}")
    if not 0 <= unit.rhash <= 0xFFFFFFFF:
        raise ValueError(f"rhash out of UInt32 range: {unit.rhash!r}")
    if not -0x80000000 <= unit.strid <= 0x7FFFFFFF:
        raise ValueError(f"strid out of Int32 range: {unit.strid!r}")
    return POINTER_LITE_STRUCT.pack(
        unit.strid,
        unit.formid,
        _encode_sig(unit.signature, field_label="signature"),
        _encode_sig(unit.field, field_label="field"),
        unit.index,
        unit.index_max,
        unit.rhash,
    )


def _write_utf16_block(out: BinaryIO, text: str) -> None:
    payload = text.encode("utf-16-le")
    out.write(struct.pack("<i", len(payload)))
    out.write(payload)


def _write_master_table(out: BinaryIO, masters: Sequence[str]) -> None:
    out.write(struct.pack("<i", len(masters)))
    for name in masters:
        _write_utf16_block(out, name)


def _write_colab_table(out: BinaryIO, labels: Sequence[tuple[int, str]]) -> None:
    out.write(struct.pack("<i", len(labels)))
    for colab_id, label in labels:
        if not -0x80000000 <= colab_id <= 0x7FFFFFFF:
            raise ValueError(f"colab id out of Int32 range: {colab_id!r}")
        out.write(struct.pack("<i", colab_id))
        _write_utf16_block(out, label)


def _write_entry(out: BinaryIO, unit: SSTUnit) -> None:
    out.write(bytes([unit.list_index]))
    out.write(encode_pointer_lite(unit))
    if not 0 <= unit.colab_id <= 0xFF:
        raise ValueError(f"colab_id out of byte range: {unit.colab_id!r}")
    out.write(bytes([unit.colab_id]))
    out.write(bytes([to_byte(unit.s_params)]))
    _write_utf16_block(out, unit.source)
    _write_utf16_block(out, unit.dest)


def write_sst(
    path: Path,
    units: Iterable[SSTUnit],
    masters: Sequence[str],
    *,
    colab_labels: Sequence[tuple[int, str]] | None = None,
    sst_version: SSTWriteVersion = "SSU9",
) -> None:
    """Serialize ``units`` to a byte-exact xTranslator SST at ``path``.

    Parameters
    ----------
    path:
        Destination ``.sst`` filename. Written atomically through a buffered
        stream; the caller is responsible for the surrounding directory.
    units:
        Stream of :class:`SSTUnit`. Order is preserved verbatim.
    masters:
        Master plugin filenames in load order. Required for ``SSU9``; ignored
        with no-op semantics on ``SSU8`` (per Pascal ``if version > 7``).
    colab_labels:
        Optional collaboration label table. Pass ``None`` or empty for the
        common no-collab case.
    sst_version:
        Either ``"SSU9"`` (default emit target) or ``"SSU8"`` (downgrade for
        pre-v1.6.0 xTranslator installs; drops the masterList section).
    """
    if sst_version not in _VERSION_LABELS:
        raise ValueError(
            f"unsupported write version {sst_version!r}; expected one of {_VERSION_LABELS}"
        )
    labels = list(colab_labels or ())
    with open(path, "wb") as handle:
        out: BufferedWriter = handle
        out.write(struct.pack("<I", magic_for_label(sst_version)))
        out.write(b"\x00")  # v4 placeholder flag byte
        if sst_version == "SSU9":
            _write_master_table(out, masters)
        _write_colab_table(out, labels)
        for unit in units:
            _write_entry(out, unit)


@dataclass(slots=True)
class _WriterStats:
    """Internal accounting hook reserved for future telemetry."""

    entries_written: int = 0
    masters_written: int = 0
    colab_labels_written: int = 0
    extra: dict[str, int] = field(default_factory=dict)
