"""Optional smoke test against the user-provided Starfield fixture."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest


def test_adwryos_fixture_smoke() -> None:
    from bgs_translator.parsers.encoding import DEFAULT_ENCODING_CHAINS
    from bgs_translator.parsers.extractor import extract_translation_units
    from bgs_translator.parsers.tes4_family import TES4FamilyWalker

    fixture = Path(r"D:\Starfield MO2\mods\adwryos-cc\adwryos.esm")
    if not fixture.exists():
        pytest.skip("adwryos.esm fixture not present")

    records = list(TES4FamilyWalker(fixture, encoding_chain=DEFAULT_ENCODING_CHAINS["Starfield"]).walk())
    assert len(records) > 100

    units = list(extract_translation_units(fixture, "Starfield"))
    assert len(units) > 50
    distribution = Counter(unit.signature for unit in units)
    print(f"adwryos signature distribution: {dict(sorted(distribution.items()))}")
