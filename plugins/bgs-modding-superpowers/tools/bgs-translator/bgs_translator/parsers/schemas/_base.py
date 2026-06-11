"""Per-game schema infrastructure.

Each schema loads a committed YAML manifest once per process and exposes the
``GameSchema`` protocol used by the D.1 translation-unit extractor.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from bgs_translator.parsers.extractor import GameSchema, TranslatableField

_DATA_DIR = Path(__file__).parent / "data"


@cache
def load_yaml_manifest(name: str) -> dict[str, Any]:
    """Load ``data/<name>.yaml`` and cache the parsed manifest."""

    path = _DATA_DIR / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream)
    if not isinstance(loaded, dict):
        msg = f"schema manifest {path} did not contain a mapping"
        raise ValueError(msg)
    return loaded


class YAMLBackedSchema(GameSchema):
    """Concrete schema backed by a generated YAML cpTranslate manifest."""

    def __init__(self, name: str, manifest_name: str) -> None:
        self.name = name
        self.manifest_name = manifest_name
        self._manifest = load_yaml_manifest(manifest_name)
        self._records = self._build_records(self._manifest)
        self._recorddefs = load_xtranslator_recorddefs(manifest_name)

    def get_translatable_subrecords(self, record_sig: str) -> list[TranslatableField]:
        """Return the configured translatable fields for ``record_sig``."""

        record_sig = record_sig.upper()
        if self._recorddefs:
            exact = list(self._recorddefs.get(record_sig, []))
            exact_field_sigs = {field.subrecord_sig for field in exact}
            fallback = [
                field
                for field in self._recorddefs.get("****", [])
                if field.subrecord_sig not in exact_field_sigs
            ]
            return exact + fallback
        return list(self._records.get(record_sig, []))

    @property
    def form_version_range(self) -> tuple[int, int]:
        """Return the inclusive form-version range from the manifest."""

        low, high = self._manifest["form_version_range"]
        return int(low), int(high)

    @property
    def schema_version(self) -> str:
        """Return the manifest schema version."""

        return str(self._manifest["schema_version"])

    @staticmethod
    def _build_records(manifest: dict[str, Any]) -> dict[str, list[TranslatableField]]:
        raw_records = manifest.get("records", {})
        if not isinstance(raw_records, dict):
            msg = "schema manifest records section must be a mapping"
            raise ValueError(msg)
        records: dict[str, list[TranslatableField]] = {}
        for record_sig, raw_fields in raw_records.items():
            if not isinstance(raw_fields, list):
                continue
            fields: list[TranslatableField] = []
            for raw_field in raw_fields:
                if not isinstance(raw_field, dict):
                    continue
                fields.append(
                    TranslatableField(
                        subrecord_sig=str(raw_field["subrecord_sig"]).upper(),
                        list_index=int(raw_field.get("list_index", 0)),
                        multi_value=bool(raw_field.get("multi_value", False)),
                        byte_budget=int(raw_field.get("byte_budget", 65520)),
                        notes=str(raw_field.get("notes", "")),
                    )
                )
            records[str(record_sig).upper()] = fields
        return records


@cache
def load_xtranslator_recorddefs(name: str) -> dict[str, list[TranslatableField]]:
    """Load an optional xTranslator-style ``Def_`` manifest.

    xTranslator does not rely on a fully expanded per-record field manifest. Its
    ``_recorddefs.txt`` files define exact record-field pairs plus a ``****``
    fallback for generic localized fields such as FULL/DESC/ATTX. Mirroring that
    behavior keeps newly introduced record signatures from being silently lost
    when a game plugin references them through normal localized string tables.
    """

    path = _DATA_DIR / f"{name}_recorddefs.txt"
    if not path.exists():
        return {}

    records: dict[str, dict[str, TranslatableField]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line or line.startswith("#") or not line.startswith("Def_:"):
            continue
        raw_def = line[len("Def_:") :]
        parts = raw_def.split("=", 2)
        if len(parts) != 3:
            continue
        field_sig, record_sig, list_spec = (part.strip().upper() for part in parts)
        if "?" in list_spec:
            continue
        match = re.match(r"([0-2])", list_spec)
        if match is None:
            continue
        record_fields = records.setdefault(record_sig, {})
        record_fields.setdefault(
            field_sig,
            TranslatableField(
                subrecord_sig=field_sig,
                list_index=int(match.group(1)),
                multi_value=True,
                byte_budget=65520,
                notes=f"xtranslator:{list_spec}",
            ),
        )
    return {record_sig: list(fields.values()) for record_sig, fields in records.items()}


__all__ = ["YAMLBackedSchema", "load_xtranslator_recorddefs", "load_yaml_manifest"]
