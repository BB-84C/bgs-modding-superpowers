"""Batch-side extraction from memory.sqlite into translation units."""

from __future__ import annotations

import sqlite3
from typing import Any

from bgs_translator.parsers.tes4_family import TranslationUnit


def collect_units_for_run(
    conn: sqlite3.Connection,
    *,
    statuses: list[str] | None = None,
    signatures: list[str] | None = None,
    fields: list[str] | None = None,
    row_ids: list[str] | None = None,
    limit: int | None = None,
    dedupe_sources: bool = True,
) -> list[TranslationUnit]:
    """Read filtered, source-deduplicated TranslationUnits from memory.sqlite."""

    clauses: list[str] = []
    params: list[Any] = []
    if statuses:
        clauses.append(f"status IN ({_placeholders(statuses)})")
        params.extend(statuses)
    if signatures:
        clauses.append(f"signature IN ({_placeholders(signatures)})")
        params.extend(signature.upper() for signature in signatures)
    if fields:
        clauses.append(f"field IN ({_placeholders(fields)})")
        params.extend(field.upper() for field in fields)
    if row_ids:
        clauses.append(f"row_id IN ({_placeholders(row_ids)})")
        params.extend(row_ids)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = "LIMIT ?" if limit is not None else ""
    if limit is not None:
        params.append(limit)
    rows = conn.execute(
        f"""
        SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
               source, index_n, index_max, list_index, strid
        FROM units
        {where}
        ORDER BY signature, field, formid, index_n
        {limit_sql}
        """,
        params,
    ).fetchall()
    seen_source_contexts: set[tuple[str, str, str]] = set()
    units: list[TranslationUnit] = []
    if row_ids:
        row_order = {row_id: index for index, row_id in enumerate(row_ids)}
        rows = sorted(rows, key=lambda row: row_order.get(str(row[0]), len(row_order)))
    for row in rows:
        source = str(row[7])
        signature = str(row[5])
        field = str(row[6])
        source_context = (source, signature, field)
        if dedupe_sources and source_context in seen_source_contexts:
            continue
        seen_source_contexts.add(source_context)
        units.append(
            TranslationUnit(
                plugin=str(row[1]),
                formid=int(row[2]),
                formid_sanitized=int(row[3]),
                edid=None if row[4] is None else str(row[4]),
                signature=signature,
                field=field,
                source=source,
                index_n=int(row[8]),
                index_max=int(row[9]),
                list_index=int(row[10]),
                strid=int(row[11]),
            )
        )
    return units


def _placeholders(values: list[str]) -> str:
    return ", ".join("?" for _value in values)


__all__ = ["collect_units_for_run"]
