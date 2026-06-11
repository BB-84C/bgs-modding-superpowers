"""Tests for Morrowind TES3 translation-unit extraction."""

from __future__ import annotations

from pathlib import Path

from test_tes3_walker import tes3_plugin, tes3_record, tes3_subrecord


class BookSchema:
    name = "Morrowind"

    def get_translatable_subrecords(self, record_sig: str):  # type: ignore[no-untyped-def]
        from bgs_translator.parsers.extractor import TranslatableField

        if record_sig == "BOOK":
            return [
                TranslatableField("FNAM", 0, False, 65520),
                TranslatableField("DESC", 0, False, 65520),
                TranslatableField("TEXT", 0, False, 65520),
            ]
        return []


def test_extract_tes3_translation_units(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_tes3_translation_units

    plugin = tmp_path / "Book.esp"
    plugin.write_bytes(
        tes3_plugin(
            tes3_record(
                b"BOOK",
                b"".join(
                    [
                        tes3_subrecord(b"NAME", b"book_skill_alchemy\x00"),
                        tes3_subrecord(b"FNAM", b"Alchemy Master\x00"),
                        tes3_subrecord(b"DESC", "Caf\xe9 description".encode("cp1252") + b"\x00"),
                    ]
                ),
            )
        )
    )

    units = list(extract_tes3_translation_units(plugin, BookSchema()))

    assert [(unit.formid, unit.formid_sanitized, unit.edid, unit.signature, unit.field, unit.source) for unit in units] == [
        (0, 0, "book_skill_alchemy", "BOOK", "FNAM", "Alchemy Master"),
        (0, 0, "book_skill_alchemy", "BOOK", "DESC", "Caf\xe9 description"),
    ]
    assert all(unit.list_index == 0 for unit in units)
