"""Provider-facing batch item payload helpers."""

from __future__ import annotations

from typing import Any

from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.signatures import signature_explanation


def batch_items_payload(batch: Batch) -> dict[str, dict[str, Any]]:
    """Return model input items with source text plus record context."""

    payload: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(batch.items, start=1):
        unit = item.unit
        signature = str(unit.signature or "").upper()
        field = str(unit.field or "").upper()
        payload[f"I{index}"] = {
            "source": item.source_masked,
            "edid": unit.edid or "",
            "signature": signature,
            "field": field,
            "record": f"{signature}:{field}" if field else signature,
            "record_explanation": signature_explanation(signature),
        }
    return payload


def compact_batch_items_payload(batch: Batch) -> list[dict[str, Any]]:
    """Return preview-friendly rows while preserving legacy source_masked."""

    rows: list[dict[str, Any]] = []
    for item_id, payload in batch_items_payload(batch).items():
        rows.append({"item_id": item_id, "source_masked": payload["source"], **payload})
    return rows


__all__ = ["batch_items_payload", "compact_batch_items_payload"]
