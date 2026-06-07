"""Per-game schema infrastructure.

Each schema loads a committed YAML manifest once per process and exposes the
``GameSchema`` protocol used by the D.1 translation-unit extractor.
"""

from __future__ import annotations

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

    def get_translatable_subrecords(self, record_sig: str) -> list[TranslatableField]:
        """Return the configured translatable fields for ``record_sig``."""

        return list(self._records.get(record_sig.upper(), []))

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


__all__ = ["YAMLBackedSchema", "load_yaml_manifest"]
