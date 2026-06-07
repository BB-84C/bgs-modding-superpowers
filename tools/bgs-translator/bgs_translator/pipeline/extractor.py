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
    limit: int | None = None,
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
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = "LIMIT ?" if limit is not None else ""
    if limit is not None:
        params.append(limit)
    rows = conn.execute(
        f"""
        SELECT plugin, formid, formid_sanitized, edid, signature, field,
               source, index_n, index_max, list_index, strid
        FROM units
        {where}
        ORDER BY signature, field, formid, index_n
        {limit_sql}
        """,
        params,
    ).fetchall()
    seen_sources: set[str] = set()
    units: list[TranslationUnit] = []
    for row in rows:
        source = str(row[6])
        if source in seen_sources:
            continue
        seen_sources.add(source)
        units.append(
            TranslationUnit(
                plugin=str(row[0]),
                formid=int(row[1]),
                formid_sanitized=int(row[2]),
                edid=None if row[3] is None else str(row[3]),
                signature=str(row[4]),
                field=str(row[5]),
                source=source,
                index_n=int(row[7]),
                index_max=int(row[8]),
                list_index=int(row[9]),
                strid=int(row[10]),
            )
        )
    return units


def _placeholders(values: list[str]) -> str:
    return ", ".join("?" for _value in values)


__all__ = ["collect_units_for_run"]
