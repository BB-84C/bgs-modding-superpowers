"""xTranslator SST reader and writer package.

This is Chunk F: SSU9 byte-exact writer + multi-version (SSU2..SSU9) reader,
plus the supporting envelope / hash / status helpers. The deeper byte layout
and authoritative source citations live in the individual modules.
"""

from __future__ import annotations

from .envelope import (
    SST_MAGIC_TO_VERSION,
    SST_VERSION_LABELS,
    SST_VERSION_TO_MAGIC,
    SSTLabel,
    SSTVersion,
    detect_label,
    detect_version,
    label_for_version,
    magic_for_label,
)
from .hash import (
    FNV_OFFSET_BASIS,
    FNV_PRIME,
    compute_rhash,
    format_no_edid_key,
    sanitize_formid,
    string_hash,
)
from .reader import SSTFile, read_sst
from .status import (
    DEFAULT_UI_COLOR,
    STATUS_PRIORITY,
    SStrParam,
    from_byte,
    to_byte,
    ui_color,
)
from .writer import (
    ENTRY_FIXED_SIZE,
    POINTER_LITE_SIZE,
    POINTER_LITE_STRUCT,
    SSTUnit,
    encode_pointer_lite,
    write_sst,
)

__all__ = [
    "DEFAULT_UI_COLOR",
    "ENTRY_FIXED_SIZE",
    "FNV_OFFSET_BASIS",
    "FNV_PRIME",
    "POINTER_LITE_SIZE",
    "POINTER_LITE_STRUCT",
    "SST_MAGIC_TO_VERSION",
    "SST_VERSION_LABELS",
    "SST_VERSION_TO_MAGIC",
    "STATUS_PRIORITY",
    "SSTFile",
    "SSTLabel",
    "SSTUnit",
    "SSTVersion",
    "SStrParam",
    "compute_rhash",
    "detect_label",
    "detect_version",
    "encode_pointer_lite",
    "format_no_edid_key",
    "from_byte",
    "label_for_version",
    "magic_for_label",
    "read_sst",
    "sanitize_formid",
    "string_hash",
    "to_byte",
    "ui_color",
    "write_sst",
]
