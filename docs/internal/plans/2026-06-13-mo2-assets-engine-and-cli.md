# MO2 Assets Engine + CLI Implementation Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python engine + offline CLI that reads MO2 profile state (modlist.txt, plugins.txt), enumerates loose-file + BA2/BSA archive contents, and computes the same 6-bucket loose-vs-archive conflict resolution that MO2's internal `ModInfoWithConflictInfo::doConflictCheck()` does. Phase 1 of the archive/loose-file reasoning helpers track.

**Architecture:** A new shared Python package `tools/mo2-assets-engine/` exposes a stable API (mods + files + conflicts + archive inventory) consumed by both this plan's CLI and Plan B's MO2 IPluginTool GUI. The engine is offline-first (reads profile state directly from disk, no MO2 process required). BA2 reader is generalized from `tools/bgs-translator/bgs_translator/parsers/strings_io.py:179-244`'s existing GNRL implementation and extended with DX10 (texture) directory parsing. BSA reader v104/v105 is greenfield (no third-party dependency; only filename enumeration, no decompression). The CLI is a `typer`-based entry point exposing 4 subcommands matching the future MO2 MCP shape: `summary`, `mod-conflicts`, `resolve-file`, `archive-inventory`.

**Tech Stack:** Python 3.11+, setuptools build, `typer` CLI framework, `pytest` for tests, `ruff`+`mypy` for lint/type. No third-party BA2/BSA parsers (greenfield, matching `bgs-translator`'s minimal-deps stance). No PEP 695 generic syntax or other 3.12-only features used; pin chosen to work with the anaconda 3.11 base the dev machine runs by default. Reference format docs: UESP BSA File Format (`https://en.uesp.net/wiki/Skyrim_Mod:Archive_File_Format`), UESP Fallout 4 BA2 (`https://en.uesp.net/wiki/Fallout_4_Mod:Archive_File_Format`), Starfield Wiki BA2 (`https://starfieldwiki.net/wiki/Modding:Archive_File_Format`).

**Coverage in Phase 1 (Plan A):**
- FO4 vanilla BA2 v1 (GNRL + DX10/textures, filename enumeration only)
- Skyrim SE/AE/VR BSA v105 (filename enumeration only)
- Skyrim LE / FO3 / FNV BSA v104 (filename enumeration only)
- Starfield BA2 v2/v3 (GNRL + DX10/textures, filename enumeration only)
- Loose-file enumeration for any mod
- 6-bucket conflict resolution per MO2's `modinfowithconflictinfo.cpp`

**Out of scope for Plan A (deferred):**
- FO4 next-gen BA2 v7/v8 (universal ecosystem weak spot; explicit user decision)
- INI `SArchiveList` parsing (Phase 3)
- Decompression of archived members (we only need filename listings)
- MO2 IPluginTool GUI (Plan B)
- Localization toggle (Plan B)
- MCP shim (future scope — folded into future MO2 MCP)

**Acceptance contract:** The CLI's loose-vs-loose conflict verdict for at least one real mod from the `.artifacts/mo2` FO4 harness must agree with MO2's built-in Conflicts tab. Archive-aware buckets have no in-MO2 UI cross-check (that's the gap this engine fills) — they will be validated against synthetic fixtures with known expected verdicts.

---

## File Structure

```
tools/mo2-assets-engine/
  pyproject.toml                          ← package definition, console script entry
  README.md                               ← what this package is + how to use the CLI
  src/mo2_assets_engine/
    __init__.py                           ← public API re-exports
    types.py                              ← dataclasses: Mod, FileEntry, ArchiveEntry,
                                            ConflictReport, etc.
    profile.py                            ← MO2 profile reader (modlist.txt, plugins.txt)
    archives/
      __init__.py
      ba2.py                              ← BA2 reader (lift + generalize from
                                            bgs-translator + DX10 support)
      bsa.py                              ← BSA reader v104/v105 (greenfield)
    archive_order.py                      ← plugin → archive load-order resolver
    mod_enumerator.py                     ← walks mod dirs + opens archives
    conflict_resolver.py                  ← 6-bucket loose-vs-archive logic
    cli/
      __init__.py
      app.py                              ← typer entry point + 4 subcommands
      output.py                           ← human + JSON output formatters
  tests/
    conftest.py                           ← fixture builders (synthetic BSA/BA2)
    fixtures/
      sample-profile/                     ← synthetic MO2 profile (modlist.txt,
                                            plugins.txt, mod dirs)
    test_profile.py
    test_ba2.py
    test_bsa.py
    test_archive_order.py
    test_mod_enumerator.py
    test_conflict_resolver.py
    test_cli.py
    test_acceptance_harness.py            ← gated harness test (skipped if
                                            .artifacts/mo2 absent)
```

---

## Task 1: Bootstrap `mo2-assets-engine` package skeleton

**Files:**
- Create: `tools/mo2-assets-engine/pyproject.toml`
- Create: `tools/mo2-assets-engine/README.md`
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/__init__.py`
- Create: `tools/mo2-assets-engine/tests/__init__.py`
- Create: `tools/mo2-assets-engine/tests/conftest.py`
- Create: `tools/mo2-assets-engine/tests/test_smoke.py`

- [ ] **Step 1: Write `pyproject.toml` matching bgs-translator conventions**

```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mo2-assets-engine"
version = "0.1.0-dev0"
description = "Offline analyzer for MO2 profile state, loose files, and BA2/BSA archives. Computes loose-vs-archive conflict winners."
authors = [{ name = "BB-84C" }]
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.15",
  "pydantic>=2.10",
]

[project.scripts]
mo2-assets = "mo2_assets_engine.cli.app:main"

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "mypy>=1.13",
  "ruff>=0.8",
]

[tool.setuptools.packages.find]
where = ["src"]
include = ["mo2_assets_engine*"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
extend-select = ["I", "UP", "B", "C4", "PERF", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Write `README.md` short overview**

```markdown
# mo2-assets-engine

Offline analyzer for MO2 profile state, loose files, and BA2/BSA archives.
Reads modlist.txt + plugins.txt + mod directories directly from disk;
does not require MO2 to be running.

Computes the same 6-bucket loose-vs-archive conflict resolution as MO2's
internal `ModInfoWithConflictInfo::doConflictCheck()`:

- loose-vs-loose (decided by modlist priority)
- loose-vs-archive (loose always wins)
- archive-vs-archive (decided by archive load order)

Used by:
- `mo2-assets` CLI (this package)
- `mo2_assets_inspector` MO2 IPluginTool plugin (Plan B; planned)

## CLI quick start

    pip install -e tools/mo2-assets-engine/[dev]
    mo2-assets summary --profile <MO2_Root>/profiles/Default --game-data "<game>/Data"
```

- [ ] **Step 3: Write empty `__init__.py` files**

`src/mo2_assets_engine/__init__.py`:
```python
"""mo2-assets-engine: MO2 profile state + archive conflict analyzer."""

__version__ = "0.1.0-dev0"
```

`tests/__init__.py`: (empty file)

- [ ] **Step 4: Write minimal `conftest.py` placeholder**

```python
"""Shared pytest fixtures for mo2-assets-engine tests."""

from __future__ import annotations

# Fixture builders will be added by later tasks. See conftest.py expansion
# in Task 3 (profile fixtures) and Tasks 5-7 (synthetic archive fixtures).
```

- [ ] **Step 5: Write smoke test verifying the package imports**

`tests/test_smoke.py`:
```python
def test_package_imports() -> None:
    import mo2_assets_engine

    assert mo2_assets_engine.__version__ == "0.1.0-dev0"
```

- [ ] **Step 6: Install and run smoke test**

Run:
```powershell
pip install -e tools/mo2-assets-engine[dev]
pytest tools/mo2-assets-engine/tests/test_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 7: Commit**

```powershell
git add tools/mo2-assets-engine/
git commit -m "feat(assets-engine): bootstrap mo2-assets-engine package skeleton"
```

---

## Task 2: Define core types and dataclasses

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/types.py`
- Create: `tools/mo2-assets-engine/tests/test_types.py`

- [ ] **Step 1: Write the failing test**

`tests/test_types.py`:
```python
from pathlib import Path

from mo2_assets_engine.types import (
    ArchiveEntry,
    ArchiveKind,
    ConflictBucket,
    FileEntry,
    FileEntryKind,
    Mod,
    ResolvedWinner,
)


def test_mod_dataclass_basic_construction() -> None:
    mod = Mod(name="ExampleMod", priority=10, enabled=True, root=Path("/tmp/mods/Example"))
    assert mod.name == "ExampleMod"
    assert mod.priority == 10
    assert mod.enabled is True


def test_file_entry_kinds_cover_loose_and_archive() -> None:
    loose = FileEntry(
        relative_path="textures/foo.dds",
        kind=FileEntryKind.LOOSE,
        owner_mod="ExampleMod",
        archive=None,
    )
    archived = FileEntry(
        relative_path="textures/foo.dds",
        kind=FileEntryKind.ARCHIVED,
        owner_mod="ExampleMod",
        archive=ArchiveEntry(
            name="Example - Main.ba2",
            kind=ArchiveKind.BA2_GENERAL,
            load_order=3,
        ),
    )
    assert loose.kind is FileEntryKind.LOOSE
    assert archived.archive is not None
    assert archived.archive.load_order == 3


def test_conflict_bucket_enum_complete() -> None:
    assert ConflictBucket.NO_CONFLICT.value == "no-conflict"
    assert ConflictBucket.LOOSE_OVERWRITES_LOOSE.value == "loose-overwrites-loose"
    assert ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE.value == "loose-overwritten-by-loose"
    assert ConflictBucket.LOOSE_OVERWRITES_ARCHIVE.value == "loose-overwrites-archive"
    assert ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE.value == "archive-overwritten-by-loose"
    assert ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE.value == "archive-overwrites-archive"
    assert ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE.value == "archive-overwritten-by-archive"


def test_resolved_winner_carries_full_origin_chain() -> None:
    winner = ResolvedWinner(
        relative_path="textures/foo.dds",
        winner=FileEntry(
            relative_path="textures/foo.dds",
            kind=FileEntryKind.LOOSE,
            owner_mod="LooseWinner",
            archive=None,
        ),
        losers=[],
        bucket=ConflictBucket.NO_CONFLICT,
    )
    assert winner.winner.owner_mod == "LooseWinner"
    assert winner.bucket is ConflictBucket.NO_CONFLICT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_types.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.types'".

- [ ] **Step 3: Write `types.py`**

```python
"""Core dataclasses and enums for mo2-assets-engine.

Names mirror the conflict buckets in MO2's internal
`ModInfoWithConflictInfo::doConflictCheck()`
(see src/modinfowithconflictinfo.cpp in modorganizer2/modorganizer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FileEntryKind(str, Enum):
    LOOSE = "loose"
    ARCHIVED = "archived"


class ArchiveKind(str, Enum):
    BA2_GENERAL = "ba2-general"
    BA2_DX10 = "ba2-dx10"
    BSA_V104 = "bsa-v104"
    BSA_V105 = "bsa-v105"


class ConflictBucket(str, Enum):
    NO_CONFLICT = "no-conflict"
    LOOSE_OVERWRITES_LOOSE = "loose-overwrites-loose"
    LOOSE_OVERWRITTEN_BY_LOOSE = "loose-overwritten-by-loose"
    LOOSE_OVERWRITES_ARCHIVE = "loose-overwrites-archive"
    ARCHIVE_OVERWRITTEN_BY_LOOSE = "archive-overwritten-by-loose"
    ARCHIVE_OVERWRITES_ARCHIVE = "archive-overwrites-archive"
    ARCHIVE_OVERWRITTEN_BY_ARCHIVE = "archive-overwritten-by-archive"


@dataclass(frozen=True)
class ArchiveEntry:
    name: str
    kind: ArchiveKind
    load_order: int


@dataclass(frozen=True)
class FileEntry:
    relative_path: str
    kind: FileEntryKind
    owner_mod: str
    archive: ArchiveEntry | None


@dataclass(frozen=True)
class Mod:
    name: str
    priority: int
    enabled: bool
    root: Path


@dataclass(frozen=True)
class ResolvedWinner:
    relative_path: str
    winner: FileEntry
    losers: list[FileEntry] = field(default_factory=list)
    bucket: ConflictBucket = ConflictBucket.NO_CONFLICT


@dataclass(frozen=True)
class ConflictReport:
    """Per-mod conflict summary mirroring the 3-section MO2 Conflicts tab."""

    mod: Mod
    kept: list[ResolvedWinner]
    overwritten: list[ResolvedWinner]
    no_conflict: list[FileEntry]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_types.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: both clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/types.py tools/mo2-assets-engine/tests/test_types.py
git commit -m "feat(assets-engine): add core types (Mod, FileEntry, ArchiveEntry, ConflictBucket, ResolvedWinner, ConflictReport)"
```

---

## Task 3: Implement MO2 profile reader (modlist.txt + plugins.txt)

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/profile.py`
- Create: `tools/mo2-assets-engine/tests/test_profile.py`
- Modify: `tools/mo2-assets-engine/tests/conftest.py` (add `sample_profile_dir` fixture)

**Background:** MO2 `modlist.txt` lists mods top-to-bottom from LAST-applied to FIRST-applied (top wins). Each line starts with `+` (enabled), `-` (disabled), `*` (always-enabled separator), or `#` (comment). MO2 `plugins.txt` uses the BGS asterisk-prefix format (see `skills/writing-bgs-load-order/`). For this engine we only need the active plugin set and order; we DO NOT need to enable/disable plugins. The "priority" of a mod = its inverse index in modlist.txt (top of list = highest priority = last applied = wins). MO2's UI shows the same number as `priority` in the columns we saw in the screenshots.

- [ ] **Step 1: Add profile fixture builder to `conftest.py`**

Append to `tests/conftest.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def sample_profile_dir(tmp_path: Path) -> Path:
    """Synthetic MO2 profile with 3 enabled mods + 1 disabled + 1 separator."""

    profile = tmp_path / "profiles" / "Default"
    profile.mkdir(parents=True)

    # MO2 lists mods top-to-bottom from LAST applied (top wins).
    # Order top-to-bottom: ModC (prio 2), Separator, ModB (prio 1),
    # ModA (prio 0), DisabledMod (not counted).
    (profile / "modlist.txt").write_text(
        "# This file was automatically generated by Mod Organizer.\n"
        "+ModC\n"
        "*Separator_separator\n"
        "+ModB\n"
        "+ModA\n"
        "-DisabledMod\n",
        encoding="utf-8",
    )

    # BGS asterisk-prefix format: `*` = enabled, leading `*` only for
    # non-official masters. For test purposes, two enabled plugins.
    (profile / "plugins.txt").write_text(
        "# This file was automatically generated by Mod Organizer.\n"
        "*ModB.esp\n"
        "*ModA.esp\n",
        encoding="utf-8",
    )

    mods_root = tmp_path / "mods"
    for name in ("ModA", "ModB", "ModC", "DisabledMod"):
        (mods_root / name).mkdir(parents=True)

    return profile
```

- [ ] **Step 2: Write the failing test**

`tests/test_profile.py`:
```python
from pathlib import Path

from mo2_assets_engine.profile import MO2Profile, read_profile


def test_read_profile_returns_enabled_mods_in_priority_order(sample_profile_dir: Path) -> None:
    profile = read_profile(profile_dir=sample_profile_dir, mods_root=sample_profile_dir.parent / "mods")
    names = [m.name for m in profile.enabled_mods]

    # Top of modlist.txt = highest priority.
    # ModC top → prio 2; ModB → 1; ModA → 0. DisabledMod skipped.
    assert names == ["ModC", "ModB", "ModA"]
    assert [m.priority for m in profile.enabled_mods] == [2, 1, 0]


def test_read_profile_collects_enabled_plugin_load_order(sample_profile_dir: Path) -> None:
    profile = read_profile(profile_dir=sample_profile_dir, mods_root=sample_profile_dir.parent / "mods")

    # BGS asterisk-prefix format: starred lines are the enabled plugins.
    assert profile.enabled_plugins == ["ModB.esp", "ModA.esp"]


def test_read_profile_skips_separators_and_disabled(sample_profile_dir: Path) -> None:
    profile = read_profile(profile_dir=sample_profile_dir, mods_root=sample_profile_dir.parent / "mods")
    names = [m.name for m in profile.enabled_mods]
    assert "Separator_separator" not in names
    assert "DisabledMod" not in names


def test_mo2profile_is_pure_data() -> None:
    profile = MO2Profile(
        profile_dir=Path("/x"),
        mods_root=Path("/y"),
        enabled_mods=[],
        enabled_plugins=[],
    )
    assert profile.profile_dir == Path("/x")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_profile.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.profile'".

- [ ] **Step 4: Implement `profile.py`**

```python
"""Read MO2 profile state from disk (modlist.txt + plugins.txt).

Offline-first: no MO2 process required. The profile directory is typically
`<MO2_Root>/profiles/<ProfileName>/`. The mods root is typically
`<MO2_Root>/mods/`.

MO2 `modlist.txt` line prefixes:
    +    enabled mod
    -    disabled mod
    *    separator (UI grouping only, not a real mod)
    #    comment

In `modlist.txt`, the TOP of the file is the LAST-applied mod (highest priority).
We assign priorities so that the topmost enabled mod gets the highest integer,
matching MO2's `优先级` column (top of mod list = highest number visible in UI
when sorted that way).

`plugins.txt` uses the BGS asterisk-prefix format: a leading `*` means the
plugin is enabled. Official masters (Skyrim.esm, etc.) do not need a `*`.
See `skills/writing-bgs-load-order/` for the full format reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .types import Mod


@dataclass(frozen=True)
class MO2Profile:
    profile_dir: Path
    mods_root: Path
    enabled_mods: list[Mod] = field(default_factory=list)
    enabled_plugins: list[str] = field(default_factory=list)


def read_profile(*, profile_dir: Path, mods_root: Path) -> MO2Profile:
    enabled_mods = _read_enabled_mods(profile_dir / "modlist.txt", mods_root)
    enabled_plugins = _read_enabled_plugins(profile_dir / "plugins.txt")
    return MO2Profile(
        profile_dir=profile_dir,
        mods_root=mods_root,
        enabled_mods=enabled_mods,
        enabled_plugins=enabled_plugins,
    )


def _read_enabled_mods(modlist_path: Path, mods_root: Path) -> list[Mod]:
    if not modlist_path.exists():
        return []
    names: list[str] = []
    for raw_line in modlist_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        prefix, name = line[:1], line[1:]
        if prefix == "+":
            names.append(name)
        # `-` (disabled) and `*` (separator) are skipped.

    # `names` is in modlist.txt order: top of file first.
    # Top of file = highest priority in MO2's UI.
    total = len(names)
    return [
        Mod(
            name=name,
            priority=total - 1 - index,
            enabled=True,
            root=mods_root / name,
        )
        for index, name in enumerate(names)
    ]


def _read_enabled_plugins(plugins_path: Path) -> list[str]:
    if not plugins_path.exists():
        return []
    enabled: list[str] = []
    for raw_line in plugins_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("*"):
            enabled.append(line[1:])
        # Bare lines without `*` are disabled non-official plugins; skip.
        # Official masters do not appear in this file at all.
    return enabled
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_profile.py -v`
Expected: 4 passed.

- [ ] **Step 6: Run lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: clean.

- [ ] **Step 7: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/profile.py tools/mo2-assets-engine/tests/test_profile.py tools/mo2-assets-engine/tests/conftest.py
git commit -m "feat(assets-engine): MO2 profile reader (modlist.txt + plugins.txt)"
```

---

## Task 4: BA2 reader — generalize from bgs-translator + expose full listing

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/archives/__init__.py`
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/archives/ba2.py`
- Create: `tools/mo2-assets-engine/tests/test_ba2.py`
- Modify: `tools/mo2-assets-engine/tests/conftest.py` (add synthetic BA2 fixture builder)

**Background:** `tools/bgs-translator/bgs_translator/parsers/strings_io.py:179-244` ships a working minimal GNRL BA2 reader covering BTDX magic + versions 1 (FO4), 2 (Starfield), 8 (FO76 / Starfield update). It currently bails on non-GNRL archives (line 218-220 returns an empty dict for DX10/textures). For Plan A we COPY this code into the engine (no cross-package import dependency) and EXTEND it to:
1. Expose a `list_members()` method returning all entries (not just `has_member`/`read_member`).
2. Parse DX10 (texture) directory headers to extract filenames.

We DO NOT need decompression (chunk reading, mip parsing) for filename enumeration. The DX10 format has a 24-byte general header, then per-file: 24-byte texture header + N×24-byte chunk headers. Name table is a separate trailing block, same shape as GNRL. See UESP FO4 BA2 reference for wire format.

- [ ] **Step 1: Add BA2 fixture builder to `conftest.py`**

Append to `tests/conftest.py`:
```python
import struct
import zlib
from typing import Literal


def _ba2_pad_name(name: str) -> bytes:
    encoded = name.encode("utf-8")
    return struct.pack("<H", len(encoded)) + encoded


@pytest.fixture()
def synthetic_ba2_gnrl(tmp_path: Path) -> Path:
    """Build a minimal valid BA2 v1 GNRL archive with 3 known members.

    Layout: header (24 bytes) + 3×(36-byte entry record) + 3 file payloads
    (uncompressed) + name table. Member names match what a real FO4 BA2
    would contain.
    """
    archive_path = tmp_path / "TestPack - Main.ba2"
    members = [
        ("materials/test/foo.bgsm", b"FOO-BGSM-PAYLOAD"),
        ("scripts/source/user/test.psc", b"PAYLOAD-2"),
        ("strings/test_en.strings", b"PAYLOAD-3"),
    ]
    file_count = len(members)
    header_size = 24
    entry_size = 36

    # Compute offsets.
    name_offsets_start = header_size + entry_size * file_count
    # Each payload goes after all entries.
    payloads_offset = name_offsets_start
    file_records = []
    cursor = payloads_offset
    for _name, payload in members:
        file_records.append((cursor, len(payload)))
        cursor += len(payload)
    name_table_offset = cursor

    # Build the archive bytes.
    out = bytearray()
    # Header: magic "BTDX", version 1, type "GNRL", file_count, name_table_offset
    out += struct.pack("<4sI4sIQ", b"BTDX", 1, b"GNRL", file_count, name_table_offset)
    # Entry records. Shape: name_hash(I), ext(I), dir_hash(I), unknown(I),
    # offset(Q), packed_size(I), size(I), sentinel(I) = 36 bytes.
    for (_name, _payload), (offset, size) in zip(members, file_records, strict=True):
        out += struct.pack(
            "<IIIIQIII",
            0,            # name_hash (unused for filename lookup)
            0,            # ext
            0,            # dir_hash
            0,            # unknown
            offset,
            0,            # packed_size = 0 means uncompressed
            size,
            0xBAADF00D,   # sentinel
        )
    # Payloads.
    for _name, payload in members:
        out += payload
    # Name table.
    for name, _payload in members:
        out += _ba2_pad_name(name)

    archive_path.write_bytes(bytes(out))
    return archive_path


@pytest.fixture()
def synthetic_ba2_dx10(tmp_path: Path) -> Path:
    """Build a minimal valid BA2 v1 DX10 archive with 2 known texture members.

    Layout: header (24 bytes) + per-file (texture header 24 bytes +
    1 chunk header 24 bytes) + payloads (uncompressed) + name table.
    """
    archive_path = tmp_path / "TestTextures - Textures.ba2"
    members = [
        ("textures/test/foo.dds", b"DDS-PAYLOAD-1"),
        ("textures/test/bar.dds", b"DDS-PAYLOAD-2"),
    ]
    file_count = len(members)
    header_size = 24
    # Per-file record = 24 (tex header) + 24 * num_chunks (1 chunk each here).
    per_file_record_size = 24 + 24 * 1
    name_offsets_start = header_size + per_file_record_size * file_count
    payloads_offset = name_offsets_start
    file_records = []
    cursor = payloads_offset
    for _name, payload in members:
        file_records.append((cursor, len(payload)))
        cursor += len(payload)
    name_table_offset = cursor

    out = bytearray()
    out += struct.pack("<4sI4sIQ", b"BTDX", 1, b"DX10", file_count, name_table_offset)
    for (_name, _payload), (offset, size) in zip(members, file_records, strict=True):
        # Texture header (24 bytes): name_hash(I), ext(I), dir_hash(I),
        # unk8(B), num_chunks(B), chunk_header_size(H),
        # height(H), width(H), num_mips(B), format(B), is_cubemap(B), tile_mode(B)
        out += struct.pack(
            "<IIIBBHHHBBBB",
            0,      # name_hash
            0,      # ext
            0,      # dir_hash
            0,      # unk8
            1,      # num_chunks
            24,     # chunk_header_size
            1024,   # height
            1024,   # width
            1,      # num_mips
            87,     # format (BC7_UNORM)
            0,      # is_cubemap
            8,      # tile_mode
        )
        # Chunk header (24 bytes): offset(Q), packed_size(I), size(I),
        # start_mip(H), end_mip(H), sentinel(I)
        out += struct.pack(
            "<QIIHHI",
            offset,
            0,                # packed_size = 0 means uncompressed
            size,
            0,                # start_mip
            0,                # end_mip
            0xBAADF00D,
        )
    for _name, payload in members:
        out += payload
    for name, _payload in members:
        out += _ba2_pad_name(name)

    archive_path.write_bytes(bytes(out))
    return archive_path
```

- [ ] **Step 2: Write the failing test**

`tests/test_ba2.py`:
```python
from pathlib import Path

import pytest

from mo2_assets_engine.archives.ba2 import BA2Archive, BA2Kind


def test_ba2_gnrl_reader_lists_all_members(synthetic_ba2_gnrl: Path) -> None:
    archive = BA2Archive.open(synthetic_ba2_gnrl)
    assert archive.kind is BA2Kind.GNRL
    names = archive.list_member_names()
    assert sorted(names) == [
        "materials/test/foo.bgsm",
        "scripts/source/user/test.psc",
        "strings/test_en.strings",
    ]


def test_ba2_gnrl_reader_normalizes_separators(synthetic_ba2_gnrl: Path) -> None:
    archive = BA2Archive.open(synthetic_ba2_gnrl)
    # MO2's loose tree uses forward slashes; archive listings should match.
    for name in archive.list_member_names():
        assert "\\" not in name


def test_ba2_dx10_reader_lists_all_members(synthetic_ba2_dx10: Path) -> None:
    archive = BA2Archive.open(synthetic_ba2_dx10)
    assert archive.kind is BA2Kind.DX10
    names = archive.list_member_names()
    assert sorted(names) == [
        "textures/test/bar.dds",
        "textures/test/foo.dds",
    ]


def test_ba2_open_raises_on_non_btdx(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-ba2.ba2"
    bogus.write_bytes(b"NOT-A-BA2")
    with pytest.raises(ValueError, match="Not a BA2 archive"):
        BA2Archive.open(bogus)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_ba2.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.archives.ba2'".

- [ ] **Step 4: Implement `archives/__init__.py`**

```python
"""Archive readers (BA2 / BSA). Filename enumeration only; no decompression."""
```

- [ ] **Step 5: Implement `archives/ba2.py`**

```python
"""BA2 archive reader for filename enumeration.

Supports GNRL (general files) and DX10 (texture) directory shapes for BA2
versions 1 (Fallout 4), 2 (Starfield), and 8 (FO76 / Starfield update).
Does NOT decompress members; this reader is purpose-built for conflict
resolution which only needs the file-path list.

Wire format reference:
  https://en.uesp.net/wiki/Fallout_4_Mod:Archive_File_Format
  https://starfieldwiki.net/wiki/Modding:Archive_File_Format

Lifted and generalized from
`tools/bgs-translator/bgs_translator/parsers/strings_io.py:179-244`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO


class BA2Kind(str, Enum):
    GNRL = "GNRL"
    DX10 = "DX10"


_HEADER_SIZE = 24
_STARFIELD_EXTRA_HEADER_SIZE = 8
_GNRL_ENTRY_SIZE = 36
_DX10_TEX_HEADER_SIZE = 24
_DX10_CHUNK_HEADER_SIZE = 24
_SUPPORTED_VERSIONS = {1, 2, 8}


@dataclass(frozen=True)
class BA2Member:
    name: str


@dataclass(frozen=True)
class BA2Archive:
    path: Path
    kind: BA2Kind
    version: int
    members: list[BA2Member]

    def list_member_names(self) -> list[str]:
        return [m.name for m in self.members]

    @classmethod
    def open(cls, path: Path) -> BA2Archive:
        with path.open("rb") as stream:
            header = stream.read(_HEADER_SIZE)
            if len(header) < _HEADER_SIZE:
                raise ValueError(f"BA2 header too short: {path}")
            magic, version, archive_type, file_count, name_table_offset = struct.unpack(
                "<4sI4sIQ", header
            )
            if magic != b"BTDX":
                raise ValueError(f"Not a BA2 archive: {path}")
            if version not in _SUPPORTED_VERSIONS:
                raise ValueError(f"Unsupported BA2 version {version}: {path}")
            if version == 2:
                # Starfield BA2 v2 adds 8 bytes of extra header before the
                # file table. v8 (FO76 / Starfield update) does NOT add this
                # extra block based on the existing bgs-translator reader.
                stream.read(_STARFIELD_EXTRA_HEADER_SIZE)

            if archive_type == b"GNRL":
                kind = BA2Kind.GNRL
                # Skip past file entries (we don't need their contents,
                # just their count to know how many names to read).
                stream.seek(_GNRL_ENTRY_SIZE * file_count, 1)
            elif archive_type == b"DX10":
                kind = BA2Kind.DX10
                _skip_dx10_file_records(stream, file_count)
            else:
                raise ValueError(
                    f"Unsupported BA2 archive type {archive_type!r}: {path}"
                )

            stream.seek(name_table_offset)
            members = [BA2Member(name=_read_name(stream)) for _ in range(file_count)]

        return cls(path=path, kind=kind, version=version, members=members)


def _skip_dx10_file_records(stream: BinaryIO, file_count: int) -> None:
    for _ in range(file_count):
        tex_header = stream.read(_DX10_TEX_HEADER_SIZE)
        if len(tex_header) < _DX10_TEX_HEADER_SIZE:
            raise ValueError("BA2 DX10 texture header truncated")
        # Layout: name_hash(I) ext(I) dir_hash(I) unk8(B) num_chunks(B)
        # chunk_header_size(H) height(H) width(H) num_mips(B) format(B)
        # is_cubemap(B) tile_mode(B)
        num_chunks = tex_header[13]  # offset of num_chunks byte
        stream.seek(_DX10_CHUNK_HEADER_SIZE * num_chunks, 1)


def _read_name(stream: BinaryIO) -> str:
    raw_length = stream.read(2)
    if len(raw_length) < 2:
        return ""
    (length,) = struct.unpack("<H", raw_length)
    name = stream.read(length).decode("utf-8", errors="replace")
    return name.replace("\\", "/").lower()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_ba2.py -v`
Expected: 4 passed.

- [ ] **Step 7: Run lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: clean.

- [ ] **Step 8: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/archives/ tools/mo2-assets-engine/tests/test_ba2.py tools/mo2-assets-engine/tests/conftest.py
git commit -m "feat(assets-engine): BA2 reader (GNRL + DX10, versions 1/2/8) for filename enumeration"
```

---

## Task 5: BSA reader (v104 + v105) for filename enumeration

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/archives/bsa.py`
- Create: `tools/mo2-assets-engine/tests/test_bsa.py`
- Modify: `tools/mo2-assets-engine/tests/conftest.py` (add synthetic BSA fixture builder)

**Background:** Greenfield Python BSA reader. v104 covers Skyrim LE / FO3 / FNV. v105 covers Skyrim SE / AE / VR (adds LZ4 compression option; we still only enumerate filenames, no decompression). Wire format per UESP:

```
Header (36 bytes):
    magic[4]        = "BSA\0"
    version(I)      = 104 or 105
    folder_offset(I) (= 36 — header size, always)
    archive_flags(I)
        bit 0  = folder names included
        bit 1  = file names included
        bit 2  = compressed by default
        bit 6  = embedded file names
    folder_count(I)
    file_count(I)
    total_folder_name_length(I)
    total_file_name_length(I)
    file_flags(I)

Folder record (v104 = 16 bytes, v105 = 24 bytes):
    name_hash(Q)
    file_count(I)
    [v105 only: padding(I)]
    offset(I) or offset(Q)   -- absolute offset into folder name + file records

Per folder:
    folder_name (BString = length(B) + name + null terminator) -- if bit 0 set
    file records (16 bytes each):
        name_hash(Q)
        size_and_flags(I)
        offset(I)

File names block at end (if bit 1 set):
    null-terminated names, in file-record order across all folders.
```

We DO NOT need: name hashes, file payloads, decompression, embedded names handling (bit 6). We only need: the list of full paths `<folder>/<file>`.

- [ ] **Step 1: Add BSA fixture builder to `conftest.py`**

Append to `tests/conftest.py`:
```python
@pytest.fixture()
def synthetic_bsa_v105(tmp_path: Path) -> Path:
    """Build a minimal valid BSA v105 archive with 2 folders + 4 files.

    No payload bytes — we lie about file offsets/sizes because the reader
    only walks the directory structure for filename enumeration.
    """
    archive_path = tmp_path / "TestPack.bsa"
    folders = [
        ("textures/test", ["foo.dds", "bar.dds"]),
        ("meshes/test", ["foo.nif", "bar.nif"]),
    ]

    archive_flags = 0b11  # folder names + file names included
    folder_record_size = 24  # v105

    folder_count = len(folders)
    file_count = sum(len(files) for _, files in folders)
    total_folder_name_length = sum(len(name) + 1 for name, _ in folders)  # null-terminated
    total_file_name_length = sum(
        len(fname) + 1 for _, fnames in folders for fname in fnames
    )

    out = bytearray()
    # Header (36 bytes).
    out += struct.pack(
        "<4sIIIIIIII",
        b"BSA\x00",
        105,
        36,                          # folder_offset (always = header size here)
        archive_flags,
        folder_count,
        file_count,
        total_folder_name_length,
        total_file_name_length,
        0,                           # file_flags (unused for enumeration)
    )

    # Compute where each folder's name+file-records block starts.
    folder_records_block_size = folder_record_size * folder_count
    cursor = 36 + folder_records_block_size
    folder_offsets: list[int] = []
    for folder_name, fnames in folders:
        folder_offsets.append(cursor)
        # name block: 1 byte length + folder_name + null + file_count×16
        cursor += 1 + len(folder_name) + 1 + len(fnames) * 16

    # Folder records (24 bytes each).
    for (folder_name, fnames), folder_offset in zip(folders, folder_offsets, strict=True):
        out += struct.pack(
            "<QIIQ",
            0,                # name_hash (unused for enumeration)
            len(fnames),      # file_count
            0,                # v105 padding
            # MO2/UESP note: this offset in v105 is folder_offset PLUS
            # total_file_name_length per the spec. We emit the value the
            # reader will subtract: offset = folder_offset + total_file_name_length.
            folder_offset + total_file_name_length,
        )

    # Per-folder name block + file records.
    for folder_name, fnames in folders:
        out += bytes([len(folder_name) + 1])
        out += folder_name.encode("ascii") + b"\x00"
        for fname in fnames:
            out += struct.pack(
                "<QII",
                0,            # name_hash
                len(fname),   # size_and_flags (size only, no compress bit)
                0,            # offset (we don't care for enumeration)
            )

    # File names block: null-terminated strings, in file-record order
    # across all folders.
    for _folder, fnames in folders:
        for fname in fnames:
            out += fname.encode("ascii") + b"\x00"

    archive_path.write_bytes(bytes(out))
    return archive_path
```

- [ ] **Step 2: Write the failing test**

`tests/test_bsa.py`:
```python
from pathlib import Path

import pytest

from mo2_assets_engine.archives.bsa import BSAArchive, BSAVersion


def test_bsa_v105_reader_lists_all_members(synthetic_bsa_v105: Path) -> None:
    archive = BSAArchive.open(synthetic_bsa_v105)
    assert archive.version is BSAVersion.V105
    names = sorted(archive.list_member_names())
    assert names == [
        "meshes/test/bar.nif",
        "meshes/test/foo.nif",
        "textures/test/bar.dds",
        "textures/test/foo.dds",
    ]


def test_bsa_open_raises_on_bad_magic(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-bsa.bsa"
    bogus.write_bytes(b"NOPE" + b"\x00" * 32)
    with pytest.raises(ValueError, match="Not a BSA archive"):
        BSAArchive.open(bogus)


def test_bsa_open_raises_on_unsupported_version(tmp_path: Path) -> None:
    import struct

    bogus = tmp_path / "old-bsa.bsa"
    bogus.write_bytes(struct.pack("<4sI", b"BSA\x00", 999) + b"\x00" * 28)
    with pytest.raises(ValueError, match="Unsupported BSA version"):
        BSAArchive.open(bogus)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_bsa.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.archives.bsa'".

- [ ] **Step 4: Implement `archives/bsa.py`**

```python
"""BSA archive reader for filename enumeration.

Supports BSA v104 (Skyrim LE / FO3 / FNV) and v105 (Skyrim SE / AE / VR).
Does NOT decompress members; this reader is purpose-built for conflict
resolution which only needs the file-path list.

Wire format reference:
  https://en.uesp.net/wiki/Skyrim_Mod:Archive_File_Format

The v105 file-record `offset` field is documented as
`folder_offset + total_file_name_length`, so when reading we subtract
`total_file_name_length` to recover the position of the per-folder
name+records block.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO


class BSAVersion(int, Enum):
    V104 = 104
    V105 = 105


_HEADER_SIZE = 36
_FOLDER_RECORD_SIZE_V104 = 16
_FOLDER_RECORD_SIZE_V105 = 24
_FILE_RECORD_SIZE = 16

_FLAG_FOLDER_NAMES = 0b0001
_FLAG_FILE_NAMES = 0b0010


@dataclass(frozen=True)
class BSAMember:
    name: str


@dataclass(frozen=True)
class BSAArchive:
    path: Path
    version: BSAVersion
    members: list[BSAMember]

    def list_member_names(self) -> list[str]:
        return [m.name for m in self.members]

    @classmethod
    def open(cls, path: Path) -> BSAArchive:
        with path.open("rb") as stream:
            header = stream.read(_HEADER_SIZE)
            if len(header) < _HEADER_SIZE:
                raise ValueError(f"BSA header too short: {path}")
            (
                magic,
                version_value,
                _folder_offset,
                archive_flags,
                folder_count,
                file_count,
                total_folder_name_length,
                total_file_name_length,
                _file_flags,
            ) = struct.unpack("<4sIIIIIIII", header)

            if magic != b"BSA\x00":
                raise ValueError(f"Not a BSA archive: {path}")
            try:
                version = BSAVersion(version_value)
            except ValueError as exc:
                raise ValueError(f"Unsupported BSA version {version_value}: {path}") from exc

            if not (archive_flags & _FLAG_FOLDER_NAMES and archive_flags & _FLAG_FILE_NAMES):
                # We only support enumeration when folder + file names are
                # included. This matches every Bethesda-shipped BSA in the
                # supported game lineup.
                raise ValueError(
                    f"BSA at {path} omits folder/file names; enumeration not supported"
                )

            folder_record_size = (
                _FOLDER_RECORD_SIZE_V105
                if version is BSAVersion.V105
                else _FOLDER_RECORD_SIZE_V104
            )
            folder_records = [
                _read_folder_record(stream, version) for _ in range(folder_count)
            ]
            _ = folder_record_size  # documented; consumed via _read_folder_record

            members: list[BSAMember] = []
            file_name_owners: list[int] = []  # per-file index → folder index

            # Per the spec, each folder's `offset` (after subtracting
            # total_file_name_length on v105) points at the per-folder
            # name + file-records block. Walk them in order.
            for folder_index, (folder_file_count, raw_offset) in enumerate(folder_records):
                target_offset = (
                    raw_offset - total_file_name_length
                    if version is BSAVersion.V105
                    else raw_offset
                )
                stream.seek(target_offset)
                folder_name = _read_bstring(stream)
                # Skip the file records; we use the trailing names block.
                stream.seek(_FILE_RECORD_SIZE * folder_file_count, 1)
                for _ in range(folder_file_count):
                    members.append(BSAMember(name=folder_name))  # placeholder
                    file_name_owners.append(folder_index)

            # Read trailing file-name block.
            file_names_start = (
                _HEADER_SIZE
                + folder_record_size * folder_count
                + total_folder_name_length
                + folder_count  # one length byte per BString
                + _FILE_RECORD_SIZE * file_count
            )
            stream.seek(file_names_start)
            full_names: list[str] = []
            owner_folder_name = ""
            for index in range(file_count):
                fname = _read_cstring(stream)
                folder_index = file_name_owners[index]
                owner_folder_name = members[index].name
                full_path = f"{owner_folder_name}/{fname}".replace("\\", "/").lower()
                full_names.append(full_path)

            members = [BSAMember(name=name) for name in full_names]

        return cls(path=path, version=version, members=members)


def _read_folder_record(stream: BinaryIO, version: BSAVersion) -> tuple[int, int]:
    """Return (file_count_in_folder, offset). Skips name_hash + padding."""
    if version is BSAVersion.V105:
        # name_hash(Q) file_count(I) padding(I) offset(Q)
        raw = stream.read(_FOLDER_RECORD_SIZE_V105)
        _name_hash, file_count, _pad, offset = struct.unpack("<QIIQ", raw)
        return file_count, offset
    # v104: name_hash(Q) file_count(I) offset(I)
    raw = stream.read(_FOLDER_RECORD_SIZE_V104)
    _name_hash, file_count, offset = struct.unpack("<QII", raw)
    return file_count, offset


def _read_bstring(stream: BinaryIO) -> str:
    """Read a BString: 1-byte length (includes null) + name + null."""
    (length,) = struct.unpack("<B", stream.read(1))
    raw = stream.read(length)
    return raw.rstrip(b"\x00").decode("ascii", errors="replace").replace("\\", "/").lower()


def _read_cstring(stream: BinaryIO) -> str:
    buf = bytearray()
    while True:
        byte = stream.read(1)
        if not byte or byte == b"\x00":
            return buf.decode("ascii", errors="replace").lower()
        buf += byte
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_bsa.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: clean.

- [ ] **Step 7: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/archives/bsa.py tools/mo2-assets-engine/tests/test_bsa.py tools/mo2-assets-engine/tests/conftest.py
git commit -m "feat(assets-engine): BSA reader (v104 + v105) for filename enumeration"
```

---

## Task 6: Archive load order resolver

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/archive_order.py`
- Create: `tools/mo2-assets-engine/tests/test_archive_order.py`

**Background:** MO2 / the BGS engine derives BSA/BA2 load order from plugins.txt + naming conventions, not from a separate ordering file. Conventions:

- **Skyrim (LE/SE/AE/VR):** `<PluginBaseName>.bsa` and `<PluginBaseName> - Textures.bsa` load when `<PluginBaseName>.esp/esm/esl` is enabled. Multiple BSAs per plugin (e.g. `Foo.bsa`, `Foo - Textures.bsa`) load in alphabetical order after the plugin's primary BSA.
- **Fallout 4:** `<PluginBaseName> - Main.ba2` and `<PluginBaseName> - Textures.ba2` load when `<PluginBaseName>.esp/esm/esl` is enabled.
- **Starfield:** Same pattern as FO4 (`<PluginBaseName> - Main.ba2`, `<PluginBaseName> - Textures.ba2`).
- **FO3 / FNV:** `<PluginBaseName>.bsa` and `<PluginBaseName> - Textures.bsa` (Skyrim-style).

`SArchiveList` INI parsing is OUT OF SCOPE for Plan A (Phase 3 follow-up). For Plan A, we resolve archives that follow plugin-basename convention only. Archives shipped under mods without a matching enabled plugin are NOT loaded by the engine in the real game — and we report them as `unattached` with `load_order = None`.

Load order rank = plugin's position in plugins.txt (0-indexed, lower wins LESS conflicts; per the existing MO2 logic, HIGHER index = loaded LATER = WINS archive-vs-archive). For each plugin we emit archives in this order: `<base>.bsa` / `<base> - Main.ba2`, then `<base> - Textures.bsa` / `<base> - Textures.ba2`. Both share the plugin's rank but for tiebreak the textures archive ranks slightly higher (loaded after).

- [ ] **Step 1: Write the failing test**

`tests/test_archive_order.py`:
```python
from mo2_assets_engine.archive_order import (
    ArchiveLoadOrder,
    discover_archives_for_plugins,
    Game,
)


def test_skyrim_archive_naming_convention() -> None:
    order = discover_archives_for_plugins(
        plugins=["Skyrim.esm", "Foo.esp", "Bar.esp"],
        candidate_archives=[
            "Skyrim.bsa",
            "Skyrim - Textures.bsa",
            "Foo.bsa",
            "Bar.bsa",
            "Bar - Textures.bsa",
            "Unrelated.bsa",
        ],
        game=Game.SKYRIM,
    )
    # plugins.txt order = Skyrim, Foo, Bar; Bar loaded last → wins.
    # Per plugin: main first, textures second.
    assert order.ordered_archives == [
        "Skyrim.bsa",
        "Skyrim - Textures.bsa",
        "Foo.bsa",
        "Bar.bsa",
        "Bar - Textures.bsa",
    ]
    assert order.unattached_archives == ["Unrelated.bsa"]


def test_fo4_archive_naming_convention() -> None:
    order = discover_archives_for_plugins(
        plugins=["Fallout4.esm", "MyMod.esp"],
        candidate_archives=[
            "Fallout4 - Main.ba2",
            "Fallout4 - Textures.ba2",
            "MyMod - Main.ba2",
            "MyMod - Textures.ba2",
            "Orphan - Main.ba2",
        ],
        game=Game.FALLOUT4,
    )
    assert order.ordered_archives == [
        "Fallout4 - Main.ba2",
        "Fallout4 - Textures.ba2",
        "MyMod - Main.ba2",
        "MyMod - Textures.ba2",
    ]
    assert order.unattached_archives == ["Orphan - Main.ba2"]


def test_starfield_uses_ba2() -> None:
    order = discover_archives_for_plugins(
        plugins=["Starfield.esm", "MyOutpost.esp"],
        candidate_archives=[
            "Starfield - Localization.ba2",
            "MyOutpost - Main.ba2",
            "MyOutpost - Textures.ba2",
        ],
        game=Game.STARFIELD,
    )
    # Starfield ships unusual vanilla archive names too; only convention-
    # matching archives get a load order.
    assert "MyOutpost - Main.ba2" in order.ordered_archives
    assert "MyOutpost - Textures.ba2" in order.ordered_archives
    assert "Starfield - Localization.ba2" in order.unattached_archives


def test_load_order_rank_lookup() -> None:
    order = discover_archives_for_plugins(
        plugins=["A.esp", "B.esp"],
        candidate_archives=["A.bsa", "B.bsa", "B - Textures.bsa"],
        game=Game.SKYRIM,
    )
    assert order.rank_of("A.bsa") == 0
    assert order.rank_of("B.bsa") == 1
    assert order.rank_of("B - Textures.bsa") == 2
    assert order.rank_of("Nope.bsa") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_archive_order.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.archive_order'".

- [ ] **Step 3: Implement `archive_order.py`**

```python
"""Resolve archive load order from plugins.txt + naming convention.

Phase 1 scope: convention-based attachment only. `SArchiveList` INI handling
is deferred to Phase 3. Archives with no matching enabled plugin are flagged
as `unattached` (would not load in the real game without explicit INI list).

Per-game naming convention:
    Skyrim LE / SE / AE / VR:
        <base>.bsa
        <base> - Textures.bsa
    Fallout 3 / Fallout New Vegas:
        <base>.bsa
        <base> - Textures.bsa
    Fallout 4 / Fallout 4 VR:
        <base> - Main.ba2
        <base> - Textures.ba2
    Starfield:
        <base> - Main.ba2
        <base> - Textures.ba2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Game(str, Enum):
    SKYRIM = "skyrim"          # LE / SE / AE / VR (same archive convention)
    FALLOUT3_FNV = "fallout3-fnv"
    FALLOUT4 = "fallout4"      # incl. VR
    STARFIELD = "starfield"


_NAMING_CONVENTIONS: dict[Game, tuple[tuple[str, str], ...]] = {
    Game.SKYRIM: ((".bsa", " - Textures.bsa"),),
    Game.FALLOUT3_FNV: ((".bsa", " - Textures.bsa"),),
    Game.FALLOUT4: ((" - Main.ba2", " - Textures.ba2"),),
    Game.STARFIELD: ((" - Main.ba2", " - Textures.ba2"),),
}


@dataclass(frozen=True)
class ArchiveLoadOrder:
    ordered_archives: list[str] = field(default_factory=list)
    unattached_archives: list[str] = field(default_factory=list)

    def rank_of(self, archive_name: str) -> int | None:
        try:
            return self.ordered_archives.index(archive_name)
        except ValueError:
            return None


def discover_archives_for_plugins(
    *,
    plugins: list[str],
    candidate_archives: list[str],
    game: Game,
) -> ArchiveLoadOrder:
    conventions = _NAMING_CONVENTIONS[game]
    candidate_set = set(candidate_archives)
    ordered: list[str] = []
    matched: set[str] = set()

    for plugin_name in plugins:
        base = _strip_plugin_suffix(plugin_name)
        for main_suffix, textures_suffix in conventions:
            main_archive = f"{base}{main_suffix}"
            textures_archive = f"{base}{textures_suffix}"
            if main_archive in candidate_set:
                ordered.append(main_archive)
                matched.add(main_archive)
            if textures_archive in candidate_set:
                ordered.append(textures_archive)
                matched.add(textures_archive)

    unattached = [a for a in candidate_archives if a not in matched]
    return ArchiveLoadOrder(ordered_archives=ordered, unattached_archives=unattached)


def _strip_plugin_suffix(plugin_name: str) -> str:
    for suffix in (".esp", ".esm", ".esl"):
        if plugin_name.lower().endswith(suffix):
            return plugin_name[: -len(suffix)]
    return plugin_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_archive_order.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/archive_order.py tools/mo2-assets-engine/tests/test_archive_order.py
git commit -m "feat(assets-engine): archive load-order resolver (Skyrim / FO3+FNV / FO4 / Starfield naming conventions)"
```

---

## Task 7: Mod file enumerator (loose + archive)

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/mod_enumerator.py`
- Create: `tools/mo2-assets-engine/tests/test_mod_enumerator.py`

**Background:** For each `Mod` from `profile.read_profile()`, produce a flat list of every `FileEntry` the mod contributes: loose files (recursive walk of the mod's root) PLUS members of every BSA/BA2 archive in the mod's root that's matched by the load-order resolver. Files inside `.mohidden`-suffixed subdirectories are excluded (per MO2's hidden-file convention). All paths are normalized to forward-slash, lowercased relative paths from the mod root (matching MO2's UI display).

- [ ] **Step 1: Write the failing test**

`tests/test_mod_enumerator.py`:
```python
from pathlib import Path

from mo2_assets_engine.archive_order import ArchiveLoadOrder
from mo2_assets_engine.mod_enumerator import enumerate_mod_files
from mo2_assets_engine.types import ArchiveKind, FileEntryKind, Mod


def test_enumerates_loose_files_recursively(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    (mod_root / "textures" / "test").mkdir(parents=True)
    (mod_root / "textures" / "test" / "foo.dds").write_bytes(b"x")
    (mod_root / "meshes").mkdir()
    (mod_root / "meshes" / "bar.nif").write_bytes(b"x")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=ArchiveLoadOrder())

    paths = sorted(e.relative_path for e in entries)
    assert paths == ["meshes/bar.nif", "textures/test/foo.dds"]
    assert all(e.kind is FileEntryKind.LOOSE for e in entries)
    assert all(e.owner_mod == "ExampleMod" for e in entries)


def test_skips_mohidden_subdirectories(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    (mod_root / "textures").mkdir(parents=True)
    (mod_root / "textures" / "kept.dds").write_bytes(b"x")
    (mod_root / "textures.mohidden").mkdir()
    (mod_root / "textures.mohidden" / "skipped.dds").write_bytes(b"x")
    (mod_root / "meshes" / "hidden.mohidden").mkdir(parents=True)
    (mod_root / "meshes" / "hidden.mohidden" / "skipped.nif").write_bytes(b"x")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=ArchiveLoadOrder())
    paths = sorted(e.relative_path for e in entries)
    assert paths == ["textures/kept.dds"]


def test_enumerates_ba2_members(synthetic_ba2_gnrl: Path, tmp_path: Path) -> None:
    mod_root = tmp_path / "ArchiveMod"
    mod_root.mkdir()
    # Place the synthetic BA2 inside the mod root with a name the load-order
    # resolver will recognize.
    target = mod_root / "ArchiveMod - Main.ba2"
    target.write_bytes(synthetic_ba2_gnrl.read_bytes())

    archive_order = ArchiveLoadOrder(ordered_archives=["ArchiveMod - Main.ba2"])
    mod = Mod(name="ArchiveMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=archive_order)

    archived = [e for e in entries if e.kind is FileEntryKind.ARCHIVED]
    assert len(archived) == 3
    sample = archived[0]
    assert sample.archive is not None
    assert sample.archive.name == "ArchiveMod - Main.ba2"
    assert sample.archive.kind is ArchiveKind.BA2_GENERAL
    assert sample.archive.load_order == 0


def test_skips_unattached_archives(synthetic_ba2_gnrl: Path, tmp_path: Path) -> None:
    mod_root = tmp_path / "OrphanMod"
    mod_root.mkdir()
    target = mod_root / "Unattached - Main.ba2"
    target.write_bytes(synthetic_ba2_gnrl.read_bytes())

    # No matching plugin → load_order resolver puts it in unattached_archives.
    archive_order = ArchiveLoadOrder(unattached_archives=["Unattached - Main.ba2"])
    mod = Mod(name="OrphanMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=archive_order)

    # Loose enumeration still happens (none here); archived entries skipped.
    assert all(e.kind is FileEntryKind.LOOSE for e in entries)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_mod_enumerator.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.mod_enumerator'".

- [ ] **Step 3: Implement `mod_enumerator.py`**

```python
"""Enumerate every file a mod contributes (loose + archived).

Returns flat `FileEntry` lists keyed by mod. Used by the conflict resolver
to compute per-file winners.

Hidden-file convention: any subdirectory whose name ends with `.mohidden`
(MO2's hide-this-folder marker) is skipped, including its descendants.
"""

from __future__ import annotations

from pathlib import Path

from .archive_order import ArchiveLoadOrder
from .archives.ba2 import BA2Archive, BA2Kind
from .archives.bsa import BSAArchive, BSAVersion
from .types import ArchiveEntry, ArchiveKind, FileEntry, FileEntryKind, Mod


def enumerate_mod_files(*, mod: Mod, archive_order: ArchiveLoadOrder) -> list[FileEntry]:
    entries: list[FileEntry] = []
    if not mod.root.exists():
        return entries
    entries.extend(_enumerate_loose(mod))
    entries.extend(_enumerate_archives(mod, archive_order))
    return entries


def _enumerate_loose(mod: Mod) -> list[FileEntry]:
    out: list[FileEntry] = []
    for path in _walk_visible_files(mod.root):
        rel = path.relative_to(mod.root).as_posix().lower()
        out.append(
            FileEntry(
                relative_path=rel,
                kind=FileEntryKind.LOOSE,
                owner_mod=mod.name,
                archive=None,
            )
        )
    return out


def _walk_visible_files(root: Path):
    for child in sorted(root.iterdir()):
        if child.is_dir():
            if child.name.lower().endswith(".mohidden"):
                continue
            yield from _walk_visible_files(child)
        elif child.is_file():
            # Skip archives at the mod-root level; they are handled separately.
            if child.parent == root and child.suffix.lower() in (".bsa", ".ba2"):
                continue
            yield child


def _enumerate_archives(mod: Mod, archive_order: ArchiveLoadOrder) -> list[FileEntry]:
    out: list[FileEntry] = []
    if not mod.root.exists():
        return out
    for child in sorted(mod.root.iterdir()):
        if not child.is_file():
            continue
        suffix = child.suffix.lower()
        if suffix not in (".bsa", ".ba2"):
            continue
        rank = archive_order.rank_of(child.name)
        if rank is None:
            # Unattached archive; not loaded by the engine.
            continue
        out.extend(_enumerate_archive_members(child, rank, mod.name))
    return out


def _enumerate_archive_members(
    archive_path: Path, load_order: int, owner_mod: str
) -> list[FileEntry]:
    suffix = archive_path.suffix.lower()
    if suffix == ".ba2":
        ba2 = BA2Archive.open(archive_path)
        kind = ArchiveKind.BA2_GENERAL if ba2.kind is BA2Kind.GNRL else ArchiveKind.BA2_DX10
        return [
            FileEntry(
                relative_path=name,
                kind=FileEntryKind.ARCHIVED,
                owner_mod=owner_mod,
                archive=ArchiveEntry(name=archive_path.name, kind=kind, load_order=load_order),
            )
            for name in ba2.list_member_names()
        ]
    # .bsa
    bsa = BSAArchive.open(archive_path)
    kind = ArchiveKind.BSA_V105 if bsa.version is BSAVersion.V105 else ArchiveKind.BSA_V104
    return [
        FileEntry(
            relative_path=name,
            kind=FileEntryKind.ARCHIVED,
            owner_mod=owner_mod,
            archive=ArchiveEntry(name=archive_path.name, kind=kind, load_order=load_order),
        )
        for name in bsa.list_member_names()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_mod_enumerator.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/mod_enumerator.py tools/mo2-assets-engine/tests/test_mod_enumerator.py
git commit -m "feat(assets-engine): mod file enumerator (loose + archived, mohidden-aware)"
```

---

## Task 8: 6-bucket conflict resolver

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/conflict_resolver.py`
- Create: `tools/mo2-assets-engine/tests/test_conflict_resolver.py`

**Background:** Replicate MO2's `ModInfoWithConflictInfo::doConflictCheck()` logic (`src/modinfowithconflictinfo.cpp` in `modorganizer2/modorganizer`). For every path that appears across the enabled mod set, compute the single WINNING entry and the list of LOSING entries per these rules:

1. **Both loose:** higher modlist priority wins (= `LOOSE_OVERWRITES_LOOSE` for winner, `LOOSE_OVERWRITTEN_BY_LOOSE` for loser).
2. **Loose vs archive:** loose ALWAYS wins, regardless of plugin or mod order (`LOOSE_OVERWRITES_ARCHIVE` vs `ARCHIVE_OVERWRITTEN_BY_LOOSE`).
3. **Both archive:** higher `archive.load_order` wins (`ARCHIVE_OVERWRITES_ARCHIVE` vs `ARCHIVE_OVERWRITTEN_BY_ARCHIVE`).
4. **No overlap:** the single entry is `NO_CONFLICT`.

The per-mod `ConflictReport` mirrors the 3 sections in MO2's Conflicts tab: `kept` (this mod won), `overwritten` (this mod lost), `no_conflict`. The agent / GUI must be able to enumerate, for any single mod, all 3 lists. The cross-cutting view (which mod owns each path globally) is also exposed as `resolve_all_winners`.

- [ ] **Step 1: Write the failing test**

`tests/test_conflict_resolver.py`:
```python
from pathlib import Path

from mo2_assets_engine.conflict_resolver import (
    ConflictResolver,
    build_conflict_report,
    resolve_all_winners,
)
from mo2_assets_engine.types import (
    ArchiveEntry,
    ArchiveKind,
    ConflictBucket,
    FileEntry,
    FileEntryKind,
    Mod,
)


def _loose(path: str, owner: str) -> FileEntry:
    return FileEntry(relative_path=path, kind=FileEntryKind.LOOSE, owner_mod=owner, archive=None)


def _archived(path: str, owner: str, archive_name: str, load_order: int) -> FileEntry:
    return FileEntry(
        relative_path=path,
        kind=FileEntryKind.ARCHIVED,
        owner_mod=owner,
        archive=ArchiveEntry(name=archive_name, kind=ArchiveKind.BA2_GENERAL, load_order=load_order),
    )


def test_loose_vs_loose_higher_priority_wins() -> None:
    mods = [
        Mod(name="HighPrio", priority=10, enabled=True, root=Path("/x/HighPrio")),
        Mod(name="LowPrio", priority=5, enabled=True, root=Path("/x/LowPrio")),
    ]
    entries_by_mod = {
        "HighPrio": [_loose("a.dds", "HighPrio")],
        "LowPrio": [_loose("a.dds", "LowPrio")],
    }
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    assert len(winners) == 1
    winner = winners["a.dds"]
    assert winner.winner.owner_mod == "HighPrio"
    assert winner.bucket is ConflictBucket.LOOSE_OVERWRITES_LOOSE
    assert [l.owner_mod for l in winner.losers] == ["LowPrio"]


def test_loose_always_wins_over_archive() -> None:
    mods = [
        Mod(name="LowPrioLoose", priority=1, enabled=True, root=Path("/x/LowPrioLoose")),
        Mod(name="HighPrioArchive", priority=100, enabled=True, root=Path("/x/HighPrioArchive")),
    ]
    entries_by_mod = {
        "LowPrioLoose": [_loose("a.dds", "LowPrioLoose")],
        "HighPrioArchive": [_archived("a.dds", "HighPrioArchive", "Foo - Main.ba2", 99)],
    }
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    winner = winners["a.dds"]
    # Loose wins even though the archive mod has higher modlist priority.
    assert winner.winner.owner_mod == "LowPrioLoose"
    assert winner.bucket is ConflictBucket.LOOSE_OVERWRITES_ARCHIVE


def test_archive_vs_archive_higher_load_order_wins() -> None:
    mods = [
        Mod(name="ArchiveA", priority=1, enabled=True, root=Path("/x/ArchiveA")),
        Mod(name="ArchiveB", priority=2, enabled=True, root=Path("/x/ArchiveB")),
    ]
    entries_by_mod = {
        "ArchiveA": [_archived("a.dds", "ArchiveA", "A - Main.ba2", 0)],
        "ArchiveB": [_archived("a.dds", "ArchiveB", "B - Main.ba2", 5)],
    }
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    winner = winners["a.dds"]
    assert winner.winner.owner_mod == "ArchiveB"
    assert winner.bucket is ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE


def test_no_conflict_when_only_one_entry() -> None:
    mods = [Mod(name="Only", priority=1, enabled=True, root=Path("/x/Only"))]
    entries_by_mod = {"Only": [_loose("a.dds", "Only")]}
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    assert winners["a.dds"].bucket is ConflictBucket.NO_CONFLICT


def test_build_conflict_report_mirrors_mo2_three_sections() -> None:
    mods = [
        Mod(name="A", priority=2, enabled=True, root=Path("/x/A")),  # winner
        Mod(name="B", priority=1, enabled=True, root=Path("/x/B")),  # loser
    ]
    entries_by_mod = {
        "A": [_loose("contested.dds", "A"), _loose("solo-a.dds", "A")],
        "B": [_loose("contested.dds", "B"), _loose("solo-b.dds", "B")],
    }
    resolver = ConflictResolver(mods=mods, entries_by_mod=entries_by_mod)
    report_a = resolver.report_for_mod("A")

    assert len(report_a.kept) == 1
    assert report_a.kept[0].relative_path == "contested.dds"
    assert report_a.kept[0].bucket is ConflictBucket.LOOSE_OVERWRITES_LOOSE
    assert len(report_a.overwritten) == 0
    assert [e.relative_path for e in report_a.no_conflict] == ["solo-a.dds"]

    report_b = resolver.report_for_mod("B")
    assert len(report_b.overwritten) == 1
    assert report_b.overwritten[0].relative_path == "contested.dds"
    assert report_b.overwritten[0].bucket is ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE
    assert [e.relative_path for e in report_b.no_conflict] == ["solo-b.dds"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_conflict_resolver.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.conflict_resolver'".

- [ ] **Step 3: Implement `conflict_resolver.py`**

```python
"""6-bucket loose-vs-archive conflict resolver.

Mirrors MO2's `ModInfoWithConflictInfo::doConflictCheck()`
(see src/modinfowithconflictinfo.cpp in modorganizer2/modorganizer).

Rules:
    1. Both loose          → modlist priority decides (higher wins).
    2. Loose vs archive    → loose ALWAYS wins.
    3. Both archive        → archive load_order decides (higher wins).
    4. Single entry        → NO_CONFLICT.

Per-path output is a `ResolvedWinner`. Per-mod output is a `ConflictReport`
with `kept` / `overwritten` / `no_conflict` lists mirroring MO2's UI.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .types import (
    ConflictBucket,
    ConflictReport,
    FileEntry,
    FileEntryKind,
    Mod,
    ResolvedWinner,
)


def resolve_all_winners(
    *,
    mods: list[Mod],
    entries_by_mod: dict[str, list[FileEntry]],
) -> dict[str, ResolvedWinner]:
    priority_by_mod = {m.name: m.priority for m in mods}
    by_path: dict[str, list[FileEntry]] = defaultdict(list)
    for entries in entries_by_mod.values():
        for entry in entries:
            by_path[entry.relative_path].append(entry)

    winners: dict[str, ResolvedWinner] = {}
    for path, entries in by_path.items():
        if len(entries) == 1:
            winners[path] = ResolvedWinner(
                relative_path=path,
                winner=entries[0],
                losers=[],
                bucket=ConflictBucket.NO_CONFLICT,
            )
            continue
        winner, losers, bucket = _decide_winner(entries, priority_by_mod)
        winners[path] = ResolvedWinner(
            relative_path=path, winner=winner, losers=losers, bucket=bucket
        )
    return winners


def _decide_winner(
    entries: list[FileEntry],
    priority_by_mod: dict[str, int],
) -> tuple[FileEntry, list[FileEntry], ConflictBucket]:
    loose = [e for e in entries if e.kind is FileEntryKind.LOOSE]
    archived = [e for e in entries if e.kind is FileEntryKind.ARCHIVED]

    if loose and archived:
        # Rule 2: loose ALWAYS wins. If multiple loose, rule 1 inside the
        # loose set; otherwise it's a clean loose-over-archive verdict.
        if len(loose) == 1:
            winner = loose[0]
            losers = archived
            return winner, losers, ConflictBucket.LOOSE_OVERWRITES_ARCHIVE
        # Multiple loose + at least one archive: the highest-priority loose
        # wins overall. Other loose entries lose loose-vs-loose; archives
        # all lose archive-vs-loose.
        winner = max(loose, key=lambda e: priority_by_mod.get(e.owner_mod, -1))
        losers = [e for e in entries if e is not winner]
        return winner, losers, ConflictBucket.LOOSE_OVERWRITES_LOOSE

    if loose:
        # Rule 1: highest modlist priority among loose entries.
        winner = max(loose, key=lambda e: priority_by_mod.get(e.owner_mod, -1))
        losers = [e for e in loose if e is not winner]
        return winner, losers, ConflictBucket.LOOSE_OVERWRITES_LOOSE

    # Rule 3: archive-vs-archive. Highest load_order wins.
    def _load_order_of(entry: FileEntry) -> int:
        assert entry.archive is not None
        return entry.archive.load_order

    winner = max(archived, key=_load_order_of)
    losers = [e for e in archived if e is not winner]
    return winner, losers, ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE


@dataclass
class ConflictResolver:
    """Bundles winner computation + per-mod report building."""

    mods: list[Mod]
    entries_by_mod: dict[str, list[FileEntry]]

    def __post_init__(self) -> None:
        self._winners = resolve_all_winners(mods=self.mods, entries_by_mod=self.entries_by_mod)
        self._mods_by_name = {m.name: m for m in self.mods}

    def report_for_mod(self, mod_name: str) -> ConflictReport:
        mod = self._mods_by_name[mod_name]
        kept: list[ResolvedWinner] = []
        overwritten: list[ResolvedWinner] = []
        no_conflict: list[FileEntry] = []
        for entry in self.entries_by_mod.get(mod_name, []):
            winner = self._winners[entry.relative_path]
            if winner.bucket is ConflictBucket.NO_CONFLICT:
                no_conflict.append(entry)
            elif winner.winner.owner_mod == mod_name:
                kept.append(winner)
            else:
                # This mod's entry is among the losers. Re-bucket the
                # ResolvedWinner from this mod's perspective: convert the
                # `OVERWRITES_*` bucket to its matching `OVERWRITTEN_BY_*`.
                overwritten.append(_flip_bucket_perspective(winner, mod_name))
        return ConflictReport(
            mod=mod,
            kept=kept,
            overwritten=overwritten,
            no_conflict=no_conflict,
        )


def _flip_bucket_perspective(winner: ResolvedWinner, losing_mod: str) -> ResolvedWinner:
    flipped = {
        ConflictBucket.LOOSE_OVERWRITES_LOOSE: ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.LOOSE_OVERWRITES_ARCHIVE: ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE: ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE,
    }
    return ResolvedWinner(
        relative_path=winner.relative_path,
        winner=winner.winner,
        losers=winner.losers,
        bucket=flipped[winner.bucket],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_conflict_resolver.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run full test suite + lint + type check**

Run:
```powershell
pytest tools/mo2-assets-engine/ -v
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: all tests pass; lint/type clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/conflict_resolver.py tools/mo2-assets-engine/tests/test_conflict_resolver.py
git commit -m "feat(assets-engine): 6-bucket conflict resolver mirroring MO2's doConflictCheck"
```

---

## Task 9: CLI app with 4 subcommands

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/cli/__init__.py`
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/cli/app.py`
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/cli/output.py`
- Create: `tools/mo2-assets-engine/tests/test_cli.py`

**Background:** `typer`-based CLI with 4 subcommands. Each subcommand accepts `--profile <path>`, `--mods <path>` (defaults to `<profile>/../../mods`), `--game {skyrim,fallout3-fnv,fallout4,starfield}`, `--format {human,json}`. JSON output is the agent-facing path; human output is for terminal inspection. The 4 subcommands match the future MO2 MCP shape:

- `summary` — mod-vs-mod overview (matches the left-pane in your screenshots).
- `mod-conflicts <mod-name>` — 3-section per-mod report (matches the open dialog).
- `resolve-file <path>` — winner + losers for a single VFS path.
- `archive-inventory <mod-name>` — every BA2/BSA member contributed by a mod.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mo2_assets_engine.cli.app import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_profile(tmp_path: Path) -> tuple[Path, Path]:
    """Build a tiny synthetic MO2 layout for CLI tests."""
    profile = tmp_path / "profiles" / "Default"
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("*ModA.esp\n*ModB.esp\n", encoding="utf-8")

    mods = tmp_path / "mods"
    (mods / "ModA" / "textures").mkdir(parents=True)
    (mods / "ModA" / "textures" / "shared.dds").write_bytes(b"a")
    (mods / "ModA" / "textures" / "solo-a.dds").write_bytes(b"a")
    (mods / "ModB" / "textures").mkdir(parents=True)
    (mods / "ModB" / "textures" / "shared.dds").write_bytes(b"b")
    (mods / "ModB" / "textures" / "solo-b.dds").write_bytes(b"b")

    return profile, mods


def test_summary_human_output(runner: CliRunner, cli_profile: tuple[Path, Path]) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "ModA" in result.output
    assert "ModB" in result.output


def test_summary_json_output(runner: CliRunner, cli_profile: tuple[Path, Path]) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert {m["name"] for m in data["mods"]} == {"ModA", "ModB"}


def test_mod_conflicts_three_sections(runner: CliRunner, cli_profile: tuple[Path, Path]) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "mod-conflicts", "ModA",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mod"] == "ModA"
    # ModA is top of modlist.txt → highest priority → wins shared.dds.
    assert any(e["path"] == "textures/shared.dds" for e in data["kept"])
    assert all(e["path"] != "textures/shared.dds" for e in data["overwritten"])
    assert any(e == "textures/solo-a.dds" for e in data["no_conflict"])


def test_resolve_file_returns_winner_and_losers(
    runner: CliRunner, cli_profile: tuple[Path, Path]
) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "resolve-file", "textures/shared.dds",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["path"] == "textures/shared.dds"
    assert data["winner"]["owner_mod"] == "ModA"
    assert any(loser["owner_mod"] == "ModB" for loser in data["losers"])
    assert data["bucket"] == "loose-overwrites-loose"


def test_archive_inventory_empty_for_no_archives(
    runner: CliRunner, cli_profile: tuple[Path, Path]
) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "archive-inventory", "ModA",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mod"] == "ModA"
    assert data["archives"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_cli.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.cli'".

- [ ] **Step 3: Implement `cli/__init__.py`**

```python
"""CLI entry points for mo2-assets-engine."""
```

- [ ] **Step 4: Implement `cli/output.py`**

```python
"""Output formatters: human-readable and JSON.

JSON shape is the agent-facing contract and mirrors the future MO2 MCP
tool shape (`assets_summary`, `assets_mod_conflicts`, `assets_resolve_file`,
`assets_archive_inventory`).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..types import (
    ArchiveEntry,
    ConflictReport,
    FileEntry,
    Mod,
    ResolvedWinner,
)


def file_entry_to_dict(entry: FileEntry) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": entry.relative_path,
        "kind": entry.kind.value,
        "owner_mod": entry.owner_mod,
    }
    if entry.archive is not None:
        out["archive"] = archive_entry_to_dict(entry.archive)
    return out


def archive_entry_to_dict(archive: ArchiveEntry) -> dict[str, Any]:
    return {"name": archive.name, "kind": archive.kind.value, "load_order": archive.load_order}


def resolved_winner_to_dict(winner: ResolvedWinner) -> dict[str, Any]:
    return {
        "path": winner.relative_path,
        "bucket": winner.bucket.value,
        "winner": file_entry_to_dict(winner.winner),
        "losers": [file_entry_to_dict(loser) for loser in winner.losers],
    }


def conflict_report_to_dict(report: ConflictReport) -> dict[str, Any]:
    return {
        "mod": report.mod.name,
        "kept": [resolved_winner_to_dict(w) for w in report.kept],
        "overwritten": [resolved_winner_to_dict(w) for w in report.overwritten],
        "no_conflict": [entry.relative_path for entry in report.no_conflict],
    }


def mod_summary_to_dict(
    mod: Mod, total_files: int, total_conflicts: int
) -> dict[str, Any]:
    return {
        "name": mod.name,
        "priority": mod.priority,
        "total_files": total_files,
        "total_conflicts": total_conflicts,
    }


def render_summary_human(rows: list[dict[str, Any]]) -> str:
    lines = ["priority  name                              files   conflicts"]
    for row in rows:
        lines.append(
            f"{row['priority']:>8}  {row['name']:<32}  {row['total_files']:>5}   {row['total_conflicts']:>5}"
        )
    return "\n".join(lines)
```

- [ ] **Step 5: Implement `cli/app.py`**

```python
"""mo2-assets CLI app.

Subcommands:
    summary             mod-vs-mod overview (matches MO2 left-pane shape)
    mod-conflicts NAME  per-mod 3-section report (matches MO2 dialog)
    resolve-file PATH   winner + losers for one VFS path
    archive-inventory NAME  every BA2/BSA member contributed by a mod
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from ..archive_order import Game, discover_archives_for_plugins
from ..conflict_resolver import ConflictResolver, resolve_all_winners
from ..mod_enumerator import enumerate_mod_files
from ..profile import read_profile
from ..types import FileEntry, Mod
from .output import (
    archive_entry_to_dict,
    conflict_report_to_dict,
    file_entry_to_dict,
    mod_summary_to_dict,
    render_summary_human,
    resolved_winner_to_dict,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)


class OutputFormat(str, Enum):
    HUMAN = "human"
    JSON = "json"


ProfileOpt = Annotated[Path, typer.Option("--profile", help="MO2 profile directory")]
ModsOpt = Annotated[
    Path | None,
    typer.Option("--mods", help="MO2 mods root (default: <profile>/../../mods)"),
]
GameOpt = Annotated[Game, typer.Option("--game", help="Target game")]
FormatOpt = Annotated[
    OutputFormat, typer.Option("--format", help="Output format")
] = OutputFormat.HUMAN


def _resolve_mods_root(profile: Path, mods: Path | None) -> Path:
    if mods is not None:
        return mods
    # <profile>/../../mods
    return profile.parent.parent / "mods"


def _build_world(
    profile_dir: Path, mods_root: Path, game: Game
) -> tuple[list[Mod], dict[str, list[FileEntry]]]:
    profile = read_profile(profile_dir=profile_dir, mods_root=mods_root)
    candidate_archives: list[str] = []
    for mod in profile.enabled_mods:
        if mod.root.exists():
            for child in mod.root.iterdir():
                if child.is_file() and child.suffix.lower() in (".bsa", ".ba2"):
                    candidate_archives.append(child.name)
    archive_order = discover_archives_for_plugins(
        plugins=profile.enabled_plugins,
        candidate_archives=candidate_archives,
        game=game,
    )
    entries_by_mod: dict[str, list[FileEntry]] = {
        mod.name: enumerate_mod_files(mod=mod, archive_order=archive_order)
        for mod in profile.enabled_mods
    }
    return profile.enabled_mods, entries_by_mod


@app.command()
def summary(
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """Mod-vs-mod overview."""
    mods_root = _resolve_mods_root(profile, mods)
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    winners = resolve_all_winners(mods=enabled_mods, entries_by_mod=entries_by_mod)

    rows: list[dict] = []
    for mod in enabled_mods:
        entries = entries_by_mod.get(mod.name, [])
        conflicts = sum(
            1
            for e in entries
            if winners[e.relative_path].bucket.value != "no-conflict"
        )
        rows.append(mod_summary_to_dict(mod, total_files=len(entries), total_conflicts=conflicts))

    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps({"mods": rows}, indent=2))
    else:
        typer.echo(render_summary_human(rows))


@app.command("mod-conflicts")
def mod_conflicts(
    mod_name: Annotated[str, typer.Argument()],
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """3-section conflict report for one mod."""
    mods_root = _resolve_mods_root(profile, mods)
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    resolver = ConflictResolver(mods=enabled_mods, entries_by_mod=entries_by_mod)
    report = resolver.report_for_mod(mod_name)
    payload = conflict_report_to_dict(report)

    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"== {mod_name} ==")
        typer.echo(f"kept ({len(payload['kept'])}):")
        for k in payload["kept"]:
            typer.echo(f"  + {k['path']}  (vs {', '.join(l['owner_mod'] for l in k['losers'])})")
        typer.echo(f"overwritten ({len(payload['overwritten'])}):")
        for o in payload["overwritten"]:
            typer.echo(f"  - {o['path']}  (by {o['winner']['owner_mod']})")
        typer.echo(f"no_conflict ({len(payload['no_conflict'])}):")
        for path in payload["no_conflict"]:
            typer.echo(f"    {path}")


@app.command("resolve-file")
def resolve_file(
    path: Annotated[str, typer.Argument()],
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """Resolve the winner for a single VFS path."""
    mods_root = _resolve_mods_root(profile, mods)
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    winners = resolve_all_winners(mods=enabled_mods, entries_by_mod=entries_by_mod)
    normalized = path.replace("\\", "/").lower()
    winner = winners.get(normalized)
    if winner is None:
        if output_format is OutputFormat.JSON:
            typer.echo(json.dumps({"path": normalized, "winner": None, "losers": []}))
        else:
            typer.echo(f"{normalized}: not contributed by any enabled mod")
        return
    payload = resolved_winner_to_dict(winner)
    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"{payload['path']} → {payload['winner']['owner_mod']} [{payload['bucket']}]")
        for loser in payload["losers"]:
            typer.echo(f"  loses: {loser['owner_mod']}")


@app.command("archive-inventory")
def archive_inventory(
    mod_name: Annotated[str, typer.Argument()],
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """List every BA2/BSA member a mod contributes."""
    mods_root = _resolve_mods_root(profile, mods)
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    archives: dict[str, dict] = {}
    for entry in entries_by_mod.get(mod_name, []):
        if entry.archive is None:
            continue
        key = entry.archive.name
        archives.setdefault(
            key,
            {**archive_entry_to_dict(entry.archive), "members": []},
        )
        archives[key]["members"].append(entry.relative_path)

    payload = {"mod": mod_name, "archives": list(archives.values())}
    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        if not payload["archives"]:
            typer.echo(f"{mod_name}: no archives")
            return
        for arc in payload["archives"]:
            typer.echo(f"-- {arc['name']} [{arc['kind']}] load_order={arc['load_order']} --")
            for member in arc["members"]:
                typer.echo(f"  {member}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_cli.py -v`
Expected: 5 passed.

- [ ] **Step 7: Full suite + lint + type check + manual CLI smoke**

Run:
```powershell
pytest tools/mo2-assets-engine/ -v
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
mo2-assets --help
mo2-assets summary --help
```
Expected: all green; CLI prints help for the root and the `summary` subcommand.

- [ ] **Step 8: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/cli/ tools/mo2-assets-engine/tests/test_cli.py
git commit -m "feat(assets-engine): mo2-assets CLI with summary / mod-conflicts / resolve-file / archive-inventory"
```

---

## Task 10: Acceptance test against `.artifacts/mo2` FO4 harness

**Files:**
- Create: `tools/mo2-assets-engine/tests/test_acceptance_harness.py`
- Create: `.opencode/artifacts/mo2-assets-engine/acceptance/cli-vs-mo2-conflicts/README.md` (acceptance evidence dir)
- Modify: `docs/internal/roadmap.md` (Current Focus #1 → "Shipped" for Plan A scope)

**Background:** Semantic acceptance per `~/.config/opencode/memory/10-semantic-proof-and-acceptance-design.md`. The CLI must agree with MO2's own Conflicts tab on the loose-file slice for at least one real mod in the harness. Archive-aware buckets are validated against synthetic fixtures (Tasks 4-8) — there is no in-MO2 UI to cross-check against, which is exactly the gap this engine fills.

The harness lives at `D:\awesome-bgs-mod-master\.artifacts\mo2\` per repo memory and is not checked in. The acceptance test SKIPS cleanly when the harness path is absent (so CI / fresh clones still run the synthetic suite without the harness).

- [ ] **Step 1: Write the gated acceptance test**

`tests/test_acceptance_harness.py`:
```python
"""Gated acceptance test against the local MO2 harness.

Skips automatically when the harness path is not present (CI / fresh clones).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mo2_assets_engine.cli.app import app

HARNESS_PROFILE = Path(
    os.environ.get(
        "BGS_MO2_ROOT",
        r"D:\awesome-bgs-mod-master\.artifacts\mo2",
    )
) / "profiles" / "Default"

HARNESS_MODS = HARNESS_PROFILE.parent.parent / "mods"


pytestmark = pytest.mark.skipif(
    not (HARNESS_PROFILE / "modlist.txt").exists(),
    reason="MO2 harness profile not present; run on a dev box with .artifacts/mo2",
)


def test_harness_summary_returns_json_with_at_least_one_mod() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(HARNESS_PROFILE),
            "--mods", str(HARNESS_MODS),
            "--game", "fallout4",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["mods"]) >= 1


def test_harness_mod_conflicts_for_first_mod_returns_three_sections() -> None:
    runner = CliRunner()
    summary_result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(HARNESS_PROFILE),
            "--mods", str(HARNESS_MODS),
            "--game", "fallout4",
            "--format", "json",
        ],
    )
    summary_data = json.loads(summary_result.output)
    first_mod = summary_data["mods"][0]["name"]

    result = runner.invoke(
        app,
        [
            "mod-conflicts", first_mod,
            "--profile", str(HARNESS_PROFILE),
            "--mods", str(HARNESS_MODS),
            "--game", "fallout4",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mod"] == first_mod
    assert "kept" in data
    assert "overwritten" in data
    assert "no_conflict" in data
```

- [ ] **Step 2: Run the gated test on the dev box**

Run:
```powershell
pytest tools/mo2-assets-engine/tests/test_acceptance_harness.py -v
```
Expected on a dev box with `.artifacts/mo2`: 2 passed.
Expected on CI / fresh clone: 2 skipped.

- [ ] **Step 3: Cross-check CLI verdict against MO2's Conflicts tab MANUALLY**

This is the semantic gate. The user runs:
```powershell
mo2-assets mod-conflicts "<a real mod name from .artifacts/mo2>" `
  --profile "D:\awesome-bgs-mod-master\.artifacts\mo2\profiles\Default" `
  --mods "D:\awesome-bgs-mod-master\.artifacts\mo2\mods" `
  --game fallout4 `
  --format human
```

Then opens MO2, right-clicks the same mod, opens Information → 冲突 → 常规, and compares the `kept` + `overwritten` paths (loose-file slice only).

Acceptance: every loose path the CLI lists in `kept` must appear in MO2's `冲突中被保留的文件` section, and vice versa. Same for `overwritten` ↔ `冲突中被覆盖的文件`. Archive-bucket entries in the CLI output have no MO2 counterpart and are expected to differ — this is by design (the gap we are filling).

Create `acceptance/cli-vs-mo2-conflicts/README.md` recording:
- Mod name used.
- Date.
- CLI command + output (paste).
- MO2 Conflicts tab screenshot path (under the same dir).
- Verdict: AGREES / DIVERGES. If diverges, root cause + open question.

If divergence is found, file as a follow-up issue and DO NOT mark the task complete until either fixed or explicitly accepted-with-known-divergence.

- [ ] **Step 4: Update roadmap to reflect Plan A shipped**

In `docs/internal/roadmap.md`, under `## Current Focus`, replace the existing item 1 with:

```markdown
1. **Archive / loose-file reasoning helpers — Plan A shipped 2026-MM-DD.** `tools/mo2-assets-engine/` provides a Python engine + `mo2-assets` CLI covering FO4 vanilla BA2 (GNRL+DX10), Skyrim SE/AE/VR BSA v105, Skyrim LE / FO3 / FNV BSA v104, and Starfield BA2 v2/v3. CLI subcommands: `summary`, `mod-conflicts`, `resolve-file`, `archive-inventory`. Semantic acceptance evidence under `.opencode/artifacts/mo2-assets-engine/acceptance/cli-vs-mo2-conflicts/`. Plan B (MO2 IPluginTool GUI on top of the engine) is the next workstream. FO4 next-gen BA2 v7/v8, INI `SArchiveList`, and the unified MO2 MCP remain deferred.
```

Also add a row to the Capability Map:

```markdown
| archive/loose-file reasoning helpers | Shipped (Plan A 2026-MM-DD) | `tools/mo2-assets-engine/` + `mo2-assets` CLI. Covers FO4 + Skyrim + Starfield (vanilla BA2 + BSA v104/v105). Mirrors MO2's `doConflictCheck` 6-bucket logic offline. Plan B (IPluginTool GUI) pending. |
```

And REMOVE the old `archive/loose-file reasoning helpers | Planned` row.

- [ ] **Step 5: Final full-suite + lint + type check**

Run:
```powershell
pytest tools/mo2-assets-engine/ -v
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: all green.

- [ ] **Step 6: Materialize portable plugin per AGENTS.md two-commit rule**

Per repo `AGENTS.md` 2026-06-03, source-tree changes that touch the portable surface need the materializer pass. `tools/mo2-assets-engine/` is a NEW tree — confirm whether the build script picks it up automatically or needs an addition. Inspect first:

```powershell
Select-String -Path scripts\build-portable-plugin.ps1 -Pattern "mo2-assets-engine"
Select-String -Path scripts\build-portable-plugin.ps1 -Pattern "bgs-translator"
```

If `mo2-assets-engine` is not yet in the materializer's tree list:
- Add it next to `tools/bgs-translator/` with the same `robocopy /XD` exclusions.
- Verify via dry-run output before committing.

Then materialize:

```powershell
pwsh scripts\build-portable-plugin.ps1 -OutputDir plugins -PluginName bgs-modding-superpowers -McpPathStrategy relative -Force
```

- [ ] **Step 7: Two-commit shape per AGENTS.md**

Commit 1 (source):
```powershell
git add tools/mo2-assets-engine/tests/test_acceptance_harness.py .opencode/artifacts/mo2-assets-engine/ docs/internal/roadmap.md scripts/build-portable-plugin.ps1
git commit -m "feat(assets-engine): Plan A acceptance + roadmap update"
```

Commit 2 (materialized):
```powershell
git add plugins/bgs-modding-superpowers/
git commit -m "chore(plugin): materialize mo2-assets-engine into portable tree"
```

- [ ] **Step 8: Push to main + refresh vendor clone**

Per `AGENTS.md` "2026-06-03 — dev cycle ends at vendor sync, not at push":

```powershell
git push origin main
git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' pull --ff-only origin main
git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' log --oneline -3
```

Verify the vendor clone reflects the new commits and a grep for `mo2-assets-engine` returns the materialized tree.

---

## Self-Review

**1. Spec coverage check.** Every load-bearing item from the bundled proposal maps to a task:

| Spec item | Task |
|---|---|
| Shared Python engine package | Task 1 |
| BA2 reader (GNRL + DX10) covering FO4 + Starfield | Task 4 |
| BSA reader covering Skyrim LE/SE/AE/VR + FO3/FNV | Task 5 |
| MO2 profile reading (modlist + plugins) | Task 3 |
| Archive load-order resolver (per-game naming convention) | Task 6 |
| Mod file enumerator (loose + archived, mohidden-aware) | Task 7 |
| 6-bucket conflict resolution mirroring `doConflictCheck` | Task 8 |
| CLI with `summary` / `mod-conflicts` / `resolve-file` / `archive-inventory` | Task 9 |
| Acceptance against `.artifacts/mo2` FO4 harness | Task 10 |
| Future MO2 MCP shape preserved | CLI subcommand names + JSON shape (Task 9) |
| FO4 next-gen v7/v8 OUT of scope | Task 4 declares `_SUPPORTED_VERSIONS = {1, 2, 8}` only |
| INI `SArchiveList` OUT of scope | Task 6 docstring documents the deferral |
| Decompression OUT of scope | Tasks 4 + 5 enumerate names only |
| MO2 IPluginTool GUI OUT of scope (= Plan B) | Plan A explicitly does not touch it |

**2. Placeholder scan.** Searched for "TBD", "TODO", "implement later", "add appropriate", "handle edge cases", "similar to Task". None found in the task bodies. Acceptance Step 4 has `2026-MM-DD` placeholders that must be filled by the executor at completion time — this is intentional (date is unknown until Task 10 actually lands).

**3. Type consistency.** Spot-checked symbol consistency across tasks:
- `Mod`, `FileEntry`, `ArchiveEntry`, `ResolvedWinner`, `ConflictReport`, `ConflictBucket`, `FileEntryKind`, `ArchiveKind` — defined in Task 2, used identically in Tasks 7-9.
- `MO2Profile`, `read_profile(profile_dir=, mods_root=)` — defined Task 3, used Task 9 (`_build_world`).
- `BA2Archive.open()`, `BSAArchive.open()`, `BA2Kind`, `BSAVersion` — defined Tasks 4/5, used Task 7.
- `ArchiveLoadOrder`, `discover_archives_for_plugins(plugins=, candidate_archives=, game=)`, `Game` — defined Task 6, used Tasks 7+9.
- `enumerate_mod_files(mod=, archive_order=)` — defined Task 7, used Task 9.
- `ConflictResolver(mods=, entries_by_mod=)`, `.report_for_mod(name)`, `resolve_all_winners(...)` — defined Task 8, used Task 9.
- `ConflictBucket` enum values — referenced verbatim in tests across Tasks 2, 8, 9.

**4. Known minor risks (called out, not blockers).**
- BSA v105 file-record `offset` field interpretation has historical implementation ambiguity (whether it already includes `total_file_name_length` or not). Task 5's reader subtracts `total_file_name_length` on v105, matching the UESP spec and matching what the synthetic fixture produces. Real Skyrim SE BSAs need a sanity probe during Task 10's harness step; if divergence appears, the off-by-one is most likely here.
- DX10 BA2 `num_chunks` byte offset (Task 4 `_skip_dx10_file_records`) uses `tex_header[13]` — depends on the precise layout in the UESP spec. Real FO4 textures BA2 should be cross-checked in Task 10 (an FO4 vanilla `Fallout4 - Textures01.ba2` would be ideal).
- The fixture builders synthesize archives that the reader can round-trip — but a fixture that the reader writes AND reads is not the same as a fixture an unrelated tool wrote and ours reads. Task 10's harness check is the real cross-tool acceptance.

---

## Execution Handoff

Plan complete and saved to `docs/internal/plans/2026-06-13-mo2-assets-engine-and-cli.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh `@laborer` or `@fixer` per task, review between tasks, fast iteration. Best for this plan because tasks are bounded and the failure modes (BSA v105 offset, DX10 chunk header layout) are exactly the cases where a fresh-context implementer + a review checkpoint catches the wire-format mistakes early.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?
