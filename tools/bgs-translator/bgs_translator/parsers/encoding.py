"""Encoding fallback chains for plugin and STRINGS text."""

from __future__ import annotations

DEFAULT_ENCODING_CHAINS: dict[str, list[str]] = {
    "SkyrimSE": ["utf-8", "cp1252"],
    "SkyrimAE": ["utf-8", "cp1252"],
    "SkyrimVR": ["utf-8", "cp1252"],
    "Fallout4": ["utf-8", "cp1252"],
    "Fallout76": ["utf-8", "cp1252"],
    "Starfield": ["utf-8", "cp1252"],
    "SkyrimLE": ["cp1252", "utf-8"],
    "Oblivion": ["cp1252", "utf-8"],
    "Fallout3": ["cp1252", "utf-8"],
    "FalloutNV": ["cp1252", "utf-8"],
    "Morrowind": ["cp1252", "utf-8"],
}


def decode_with_chain(raw: bytes, chain: list[str]) -> tuple[str, str]:
    """Decode bytes with the first encoding in ``chain`` that succeeds."""

    last_error: UnicodeDecodeError | None = None
    for encoding in chain:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    chain_label = ", ".join(chain)
    if last_error is not None:
        reason = f"unable to decode with chain: {chain_label}"
        raise UnicodeDecodeError(
            last_error.encoding,
            last_error.object,
            last_error.start,
            last_error.end,
            reason,
        ) from last_error
    raise UnicodeDecodeError("<empty-chain>", raw, 0, len(raw), "encoding chain is empty")


__all__ = ["DEFAULT_ENCODING_CHAINS", "decode_with_chain"]
