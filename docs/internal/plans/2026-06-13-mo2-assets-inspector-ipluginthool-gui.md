# MO2 Assets Inspector IPluginTool GUI Implementation Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MO2-loaded `mobase.IPluginTool` plugin that opens an in-MO2 window mirroring MO2's existing per-mod Conflicts tab, but extended to include BA2/BSA archive contents and the 6-bucket loose-vs-archive resolution. The GUI is the human-audit surface for the same conflict data the `mo2-assets` CLI from Plan A exposes to agents — both must agree on every verdict.

**Architecture:** Plan B is a thin frontend on top of Plan A's `mo2-assets-engine`. A new file `tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py` subclasses `mobase.IPluginTool`; its `display()` opens a non-modal `QMainWindow` parented to MO2's main window. The plugin uses `mobase.IOrganizer` ONLY to resolve the active profile directory, mods root, and game code — it then feeds those paths into the exact same `mo2_assets_engine.profile.read_profile()` + `mo2_assets_engine.mod_enumerator.enumerate_mod_files()` + `mo2_assets_engine.conflict_resolver.ConflictResolver()` calls the CLI uses. There is intentionally NO duplicated logic in the plugin: the engine is the single source of truth, the plugin is presentation.

**Tech Stack:** Python 3.12 (matches MO2's embedded `pythonXY.dll`; current MO2 ships Python 3.12), PyQt6 (matches MO2's Qt6 stack), `mobase` (MO2's Python binding, available at runtime inside the MO2 process). No new third-party deps. `mobase-stubs` for development-time type checking. Reference: MO2 plugin wiki at `https://github.com/ModOrganizer2/modorganizer/wiki/Writing-Mod-Organizer-Plugins`, Python API at `https://www.modorganizer.org/python-plugins-doc/`.

**Hard dependency on Plan A:** The `mo2_assets_engine` Python package from Plan A (Tasks 1-8 of `2026-06-13-mo2-assets-engine-and-cli.md`) must be COMPLETE and PASSING TESTS before Plan B can be exercised end-to-end. Plan B's Task 1 (engine bundling) requires the engine tree to exist. Plan A and Plan B can be authored in parallel; they MUST be tested together at acceptance.

**UX shape** (mirrors the user's MO2 screenshots, see `.opencode/images/ses_145d1713cffeeMkV4kzBuDFmNO/clipboard-{6a2b46ae,708283ef}.png`):

```
[Tools menu] → "BGS Assets Inspector"
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  BGS Assets Inspector                              [Refresh] [×]│
├─────────────────────────────────────────────────────────────────┤
│ Mods (sorted by priority, top wins)                             │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │  prio  name                       files   conflicts  type  │  │
│ │  453   远西义勇兵 - 西部风格...    111     12         mixed │  │
│ │  452   义勇兵大修 - 汉化           0       0          loose │  │
│ │  451   义勇兵大修                  300     0          archive│ │
│ │  ...                                                       │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│ (Double-click a mod to open its Conflicts dialog.)              │
└─────────────────────────────────────────────────────────────────┘

      ┌──── Double-click a mod ────►
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Conflicts — 远西义勇兵 - 西部风格义勇兵大修              [×]   │
├─────────────────────────────────────────────────────────────────┤
│  ▼ 冲突中被保留的文件 (111)                                     │
│     文件                          被覆盖的模组                  │
│     /materials/Elianora/...       艾莉诺拉的护甲店       [BA2]  │
│     /materials/Elianora/...       艾莉诺拉的护甲店       [loose]│
│     ...                                                         │
│  ▼ 冲突中被覆盖的文件 (1)                                       │
│     /Far West Minutemen.esp       远西义勇兵 - 汉化      [loose]│
│  ▼ 下列文件无冲突 (300)                                         │
│     /Tools/BodySlide/...          —                             │
│                                                                 │
│  (Click any entry to see the resolution rationale + KB ID.)     │
└─────────────────────────────────────────────────────────────────┘
```

**Out of scope for Plan B (deferred):**
- Auto-refresh on `mobase` signals (Phase 2; a `Refresh` button covers MVP).
- Tree-style file-tree view (Phase 2; Plan B uses flat path lists matching MO2's existing dialog).
- Direct "fix conflict" actions (rename, hide, mod-reorder) (Phase 3).
- INI `SArchiveList` resolution (deferred with Plan A).
- FO4 next-gen BA2 v7/v8 (deferred with Plan A).
- Future unified MO2 MCP (would subsume Plan B's surface).

**Acceptance contract:** Open the plugin against the `.artifacts/mo2` FO4 harness, pick a real mod with known loose-file conflicts, and verify the GUI's `kept`/`overwritten`/`no_conflict` paths agree with MO2's built-in `信息 → 冲突 → 常规` tab for the loose-file slice. Archive-bucket entries have no MO2 cross-check (that's the gap this plugin fills) and are validated by agreement with Plan A's CLI on the same harness.

---

## File Structure

```
tools/mo2-control-plane/live-bridge/
  mo2_assets_inspector.py                ← IPluginTool subclass + createPlugin()
  mo2_assets_inspector/                  ← support tree, mirrors mo2_agent_control's pattern
    __init__.py
    bridge.py                            ← mobase paths resolver
    main_window.py                       ← QMainWindow + mod-list view
    mod_detail_dialog.py                 ← QDialog with 3-section conflict view
    file_detail_panel.py                 ← winner/losers/rationale panel
    localization.py                      ← zh-Hans / en string table
    vendored/
      mo2_assets_engine/                 ← copied at deploy time from
                                           tools/mo2-assets-engine/src/mo2_assets_engine/

tools/mo2-assets-engine/                 ← additive contribution from Plan B
  src/mo2_assets_engine/
    rationale.py                         ← NEW: bucket → human-readable rationale
                                           + KB record ID
  tests/
    test_rationale.py

scripts/
  deploy-mo2-assets-inspector.ps1        ← deployment script (mirrors
                                           deploy-live-bridge.ps1 pattern)

tests/
  (no new pytest dir; GUI tests are smoke-only and live next to the
   support modules above where they can be unit-tested without a live MO2.)
```

---

## Task 1: Add rationale module to the shared engine

**Files:**
- Create: `tools/mo2-assets-engine/src/mo2_assets_engine/rationale.py`
- Create: `tools/mo2-assets-engine/tests/test_rationale.py`

**Background:** Both the CLI (future) and the GUI need to explain WHY a particular bucket applies. The text is short and the KB record IDs are stable (they live in `knowledge/bgs-kb/packs/core/records/archive-precedence/`). This module is the durable mapping. Keeps explanation prose out of the Qt UI code.

- [ ] **Step 1: Write the failing test**

`tests/test_rationale.py`:
```python
from mo2_assets_engine.rationale import (
    BucketRationale,
    rationale_for_bucket,
)
from mo2_assets_engine.types import ConflictBucket


def test_each_bucket_has_a_rationale() -> None:
    for bucket in ConflictBucket:
        rationale = rationale_for_bucket(bucket)
        assert isinstance(rationale, BucketRationale)
        assert rationale.short
        assert rationale.kb_record_ids


def test_loose_overwrites_archive_cites_loose_over_archive_record() -> None:
    rationale = rationale_for_bucket(ConflictBucket.LOOSE_OVERWRITES_ARCHIVE)
    assert "archive-precedence.loose-over-archive.v1" in rationale.kb_record_ids


def test_archive_overwrites_archive_cites_plugin_order_record() -> None:
    rationale = rationale_for_bucket(ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE)
    assert "archive-precedence.plugin-order-is-not-asset-order.v1" in rationale.kb_record_ids


def test_no_conflict_has_empty_short_but_still_yields_kb_id() -> None:
    rationale = rationale_for_bucket(ConflictBucket.NO_CONFLICT)
    assert rationale.short  # not empty — explains "no overlap"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-assets-engine/tests/test_rationale.py -v`
Expected: FAIL with "No module named 'mo2_assets_engine.rationale'".

- [ ] **Step 3: Implement `rationale.py`**

```python
"""Per-bucket explanation + KB record citation.

Bucket → short human-readable rationale + canonical KB record IDs that
explain the underlying rule. KB record IDs are stable identifiers from
`knowledge/bgs-kb/packs/core/records/archive-precedence/`.

Consumers (CLI, GUI, future MO2 MCP) use this to render "why this verdict"
without re-deriving the engine rules in presentation code.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import ConflictBucket


@dataclass(frozen=True)
class BucketRationale:
    short: str
    kb_record_ids: tuple[str, ...]


_RATIONALES: dict[ConflictBucket, BucketRationale] = {
    ConflictBucket.NO_CONFLICT: BucketRationale(
        short="Only one enabled mod contributes this path; no conflict.",
        kb_record_ids=("archive-precedence.plugin-order-is-not-asset-order.v1",),
    ),
    ConflictBucket.LOOSE_OVERWRITES_LOOSE: BucketRationale(
        short=(
            "Both mods ship this path as a loose file. The mod with the higher "
            "modlist priority wins (= the one closer to the top of modlist.txt)."
        ),
        kb_record_ids=(
            "load-order.mo2-left-pane-vs-right-pane.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
    ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE: BucketRationale(
        short=(
            "This mod ships this path as a loose file, but another loose file "
            "from a higher-priority mod wins. Adjust modlist priority to flip."
        ),
        kb_record_ids=(
            "load-order.mo2-left-pane-vs-right-pane.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
    ConflictBucket.LOOSE_OVERWRITES_ARCHIVE: BucketRationale(
        short=(
            "Loose files ALWAYS win over archived assets, regardless of plugin "
            "or archive load order. The loose copy wins."
        ),
        kb_record_ids=("archive-precedence.loose-over-archive.v1",),
    ),
    ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE: BucketRationale(
        short=(
            "This entry is inside a BSA/BA2 archive, but another mod ships the "
            "same path as a loose file. Loose ALWAYS wins; the archived entry "
            "loses regardless of plugin load order."
        ),
        kb_record_ids=("archive-precedence.loose-over-archive.v1",),
    ),
    ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE: BucketRationale(
        short=(
            "Both contributions come from archives. The archive loaded LATER "
            "wins; archive load order is derived from plugin order in plugins.txt "
            "via naming convention (<base>.bsa or <base> - Main.ba2 etc.)."
        ),
        kb_record_ids=(
            "archive-precedence.bsa-vs-ba2-by-game.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
    ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE: BucketRationale(
        short=(
            "This entry is inside an archive that loses to another archive "
            "loaded later. Move the owning plugin later in plugins.txt to flip."
        ),
        kb_record_ids=(
            "archive-precedence.bsa-vs-ba2-by-game.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
}


def rationale_for_bucket(bucket: ConflictBucket) -> BucketRationale:
    return _RATIONALES[bucket]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tools/mo2-assets-engine/tests/test_rationale.py -v`
Expected: 4 passed.

- [ ] **Step 5: Lint + type check**

Run:
```powershell
ruff check tools/mo2-assets-engine/
mypy tools/mo2-assets-engine/src/
```
Expected: clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-assets-engine/src/mo2_assets_engine/rationale.py tools/mo2-assets-engine/tests/test_rationale.py
git commit -m "feat(assets-engine): per-bucket rationale + KB record citation"
```

---

## Task 2: Bootstrap inspector support tree + deployment script

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py` (top-level plugin entry; minimal createPlugin stub for now — fleshed out in Task 5)
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/__init__.py`
- Create: `scripts/deploy-mo2-assets-inspector.ps1`

**Background:** Per the librarian recon, MO2 looks for plugins in `<MO2_Root>\plugins\`. Each plugin can be either a single `.py` file or a package directory. We use the same hybrid the existing `mo2_agent_control.py` uses: a single-file plugin entry that imports from a sibling support package. The support package is what gets copied into `<MO2_Root>\plugins\Mo2AssetsInspector\`. The shared `mo2_assets_engine` Python package is COPIED into `mo2_assets_inspector/vendored/` at deploy time so the plugin is self-contained inside MO2's embedded Python (no `pip install` into MO2's Python required — matches the bootstrap pattern of `mo2_agent_control.py`).

- [ ] **Step 1: Write `mo2_assets_inspector.py` stub (top-level entry)**

`tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py`:
```python
"""MO2 Assets Inspector — IPluginTool plugin entry.

Deployed at runtime to `<MO2_Root>/plugins/mo2_assets_inspector.py` alongside
the support tree at `<MO2_Root>/plugins/Mo2AssetsInspector/`.

This top-level file is a thin entry that:
  1. Inserts the support tree's `vendored/` dir onto sys.path so the bundled
     `mo2_assets_engine` package becomes importable inside MO2's Python.
  2. Imports and re-exports `createPlugin` from the support package.

All real plugin behavior lives under `Mo2AssetsInspector/` (the support tree).
"""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_NAME = "Mo2AssetsInspector"
PLUGIN_SOURCE_SUBTREE = "tools/mo2-control-plane/live-bridge/"
PLUGIN_DEPLOYMENT_TARGET = "plugins/mo2_assets_inspector.py"
PLUGIN_SUPPORT_TARGET = "plugins/Mo2AssetsInspector/"

_SUPPORT_DIR = Path(__file__).resolve().parent / PLUGIN_NAME
_VENDORED_DIR = _SUPPORT_DIR / "vendored"

if _VENDORED_DIR.exists() and str(_VENDORED_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDORED_DIR))

# Late import: support tree must be on sys.path before this resolves.
from Mo2AssetsInspector.plugin import create_plugin as _create_plugin  # noqa: E402


def createPlugin():  # noqa: N802 — MO2 plugin contract requires this name
    return _create_plugin()
```

- [ ] **Step 2: Write `Mo2AssetsInspector/__init__.py`**

`tools/mo2-control-plane/live-bridge/mo2_assets_inspector/__init__.py`:
```python
"""MO2 Assets Inspector support package.

Public surface for the top-level plugin entry: `plugin.create_plugin()`.
"""
```

- [ ] **Step 3: Write deployment script**

`scripts/deploy-mo2-assets-inspector.ps1`:
```powershell
<#
.SYNOPSIS
Deploys the MO2 Assets Inspector plugin into <MO2_Root>/plugins/.

Copies:
  - tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py
    → <MO2_Root>/plugins/mo2_assets_inspector.py
  - tools/mo2-control-plane/live-bridge/mo2_assets_inspector/
    → <MO2_Root>/plugins/Mo2AssetsInspector/
  - tools/mo2-assets-engine/src/mo2_assets_engine/
    → <MO2_Root>/plugins/Mo2AssetsInspector/vendored/mo2_assets_engine/

MO2 must NOT be running when this script executes (file lock on plugin tree).

.PARAMETER MO2Root
Absolute path to the MO2 install root. Defaults to $env:BGS_MO2_ROOT.
#>
[CmdletBinding()]
param(
    [string]$MO2Root = $env:BGS_MO2_ROOT
)

$ErrorActionPreference = "Stop"

if (-not $MO2Root) {
    throw "MO2Root not provided and \$env:BGS_MO2_ROOT is unset."
}

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$srcEntry = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py"
$srcSupport = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_assets_inspector"
$srcEngine = Join-Path $repoRoot "tools/mo2-assets-engine/src/mo2_assets_engine"

$dstPluginsDir = Join-Path $MO2Root "plugins"
$dstEntry = Join-Path $dstPluginsDir "mo2_assets_inspector.py"
$dstSupport = Join-Path $dstPluginsDir "Mo2AssetsInspector"
$dstVendored = Join-Path $dstSupport "vendored/mo2_assets_engine"

if (-not (Test-Path -LiteralPath $dstPluginsDir)) {
    throw "MO2 plugins dir not found at: $dstPluginsDir"
}

Write-Host "Deploying mo2_assets_inspector.py → $dstEntry"
Copy-Item -LiteralPath $srcEntry -Destination $dstEntry -Force

Write-Host "Deploying support tree → $dstSupport"
if (Test-Path -LiteralPath $dstSupport) {
    Remove-Item -LiteralPath $dstSupport -Recurse -Force
}
# Use robocopy for clean dev-cache exclusion.
& robocopy $srcSupport $dstSupport /MIR `
    /XD __pycache__ .mypy_cache .pytest_cache .ruff_cache vendored `
    | Out-Null

Write-Host "Vendoring mo2_assets_engine → $dstVendored"
New-Item -ItemType Directory -Force -Path (Split-Path $dstVendored) | Out-Null
& robocopy $srcEngine $dstVendored /MIR `
    /XD __pycache__ .mypy_cache .pytest_cache .ruff_cache `
    | Out-Null

Write-Host "Deployment complete. Restart MO2 to load the plugin."
```

- [ ] **Step 4: Smoke-verify deployment script (dry-run)**

Run (with MO2 NOT running):
```powershell
$env:BGS_MO2_ROOT = "D:\awesome-bgs-mod-master\.artifacts\mo2"
pwsh scripts/deploy-mo2-assets-inspector.ps1 -WhatIf
```

Note: `-WhatIf` is not natively respected by `robocopy`; for true dry-run, inspect the script's Copy-Item destination paths and confirm they resolve correctly. Real first deployment happens in Task 9.

- [ ] **Step 5: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/ scripts/deploy-mo2-assets-inspector.ps1
git commit -m "feat(mo2-plugin): bootstrap mo2_assets_inspector support tree + deploy script"
```

---

## Task 3: mobase paths bridge

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/bridge.py`
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/__init__.py`
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_bridge.py`

**Background:** The mobase bridge resolves three things from a live `mobase.IOrganizer`: the active profile directory, the mods root, and the active game's `Game` enum value (for the archive load-order resolver). It does NOT walk live state via `IModList` / `IPluginList` / `IFileTree` — Plan A's engine reads the same on-disk state and is the single source of truth. The plugin merely points the engine at the right paths.

`mobase.IOrganizer` API (per Python plugin docs `https://www.modorganizer.org/python-plugins-doc/autoapi/mobase/index.html`):
- `organizer.profilePath()` → str — active profile dir
- `organizer.modsPath()` → str — mods root
- `organizer.managedGame()` → `IPluginGame` — has `.gameShortName()` returning e.g. `"Fallout4"`, `"SkyrimSE"`, `"Starfield"`, `"Fallout3"`, `"FalloutNV"`

We map gameShortName to the engine's `Game` enum. Unknown / unsupported games raise a clear error the plugin surfaces in the UI.

- [ ] **Step 1: Write the failing test**

`tests/test_bridge.py`:
```python
"""Unit tests for the mobase bridge.

The bridge is tested against a fake IOrganizer that mimics the mobase API
shape — we do NOT depend on a real MO2 process for these tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from Mo2AssetsInspector.bridge import (
    PathsBundle,
    UnsupportedGameError,
    bundle_paths_from_organizer,
)


def _fake_organizer(profile_path: str, mods_path: str, game_short: str) -> MagicMock:
    organizer = MagicMock()
    organizer.profilePath.return_value = profile_path
    organizer.modsPath.return_value = mods_path
    organizer.managedGame.return_value.gameShortName.return_value = game_short
    return organizer


@pytest.mark.parametrize(
    "game_short, expected_game_value",
    [
        ("Fallout4", "fallout4"),
        ("Fallout4VR", "fallout4"),
        ("SkyrimSE", "skyrim"),
        ("SkyrimAE", "skyrim"),
        ("SkyrimVR", "skyrim"),
        ("Skyrim", "skyrim"),
        ("Starfield", "starfield"),
        ("Fallout3", "fallout3-fnv"),
        ("FalloutNV", "fallout3-fnv"),
    ],
)
def test_bridge_maps_known_games(game_short: str, expected_game_value: str) -> None:
    organizer = _fake_organizer(r"C:\MO2\profiles\Default", r"C:\MO2\mods", game_short)
    bundle = bundle_paths_from_organizer(organizer)
    assert isinstance(bundle, PathsBundle)
    assert bundle.profile_dir == Path(r"C:\MO2\profiles\Default")
    assert bundle.mods_root == Path(r"C:\MO2\mods")
    assert bundle.game.value == expected_game_value


def test_bridge_raises_unsupported_game() -> None:
    organizer = _fake_organizer(r"C:\MO2\profiles\Default", r"C:\MO2\mods", "TES3Morrowind")
    with pytest.raises(UnsupportedGameError) as excinfo:
        bundle_paths_from_organizer(organizer)
    assert "TES3Morrowind" in str(excinfo.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_bridge.py -v
```
Expected: FAIL with "No module named 'Mo2AssetsInspector.bridge'".

- [ ] **Step 3: Implement `bridge.py`**

`tools/mo2-control-plane/live-bridge/mo2_assets_inspector/bridge.py`:
```python
"""Resolve mobase IOrganizer state to engine-call arguments.

Does NOT walk IModList / IPluginList / IFileTree — the engine reads the
same on-disk state and is the single source of truth. This module only
maps "which profile / which mods root / which game" so the plugin and
the CLI exercise the exact same engine code paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mo2_assets_engine.archive_order import Game


class UnsupportedGameError(RuntimeError):
    """Raised when the active game is not one the engine supports yet."""


@dataclass(frozen=True)
class PathsBundle:
    profile_dir: Path
    mods_root: Path
    game: Game


_GAME_SHORT_NAME_MAP: dict[str, Game] = {
    # Skyrim line.
    "Skyrim": Game.SKYRIM,
    "SkyrimSE": Game.SKYRIM,
    "SkyrimAE": Game.SKYRIM,
    "SkyrimVR": Game.SKYRIM,
    # Fallout 4 line.
    "Fallout4": Game.FALLOUT4,
    "Fallout4VR": Game.FALLOUT4,
    # Starfield.
    "Starfield": Game.STARFIELD,
    # Older Fallouts.
    "Fallout3": Game.FALLOUT3_FNV,
    "FalloutNV": Game.FALLOUT3_FNV,
}


def bundle_paths_from_organizer(organizer: Any) -> PathsBundle:
    profile_dir = Path(organizer.profilePath())
    mods_root = Path(organizer.modsPath())
    game_short = organizer.managedGame().gameShortName()
    game = _GAME_SHORT_NAME_MAP.get(game_short)
    if game is None:
        raise UnsupportedGameError(
            f"Game '{game_short}' is not in the engine's Phase-1 coverage. "
            f"Supported: {sorted(_GAME_SHORT_NAME_MAP)}"
        )
    return PathsBundle(profile_dir=profile_dir, mods_root=mods_root, game=game)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_bridge.py -v
```
Expected: 10 passed (9 parametrized + 1 unsupported).

- [ ] **Step 5: Lint + type check**

Run:
```powershell
ruff check tools/mo2-control-plane/live-bridge/mo2_assets_inspector/
mypy tools/mo2-control-plane/live-bridge/mo2_assets_inspector/bridge.py --explicit-package-bases
```
Expected: clean (or with documented mobase-stubs note — see Task 5 Step 1).

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector/bridge.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/
git commit -m "feat(mo2-plugin): mobase paths bridge (IOrganizer → engine PathsBundle)"
```

---

## Task 4: Localization string table

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/localization.py`
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_localization.py`

**Background:** The user's reference screenshots are zh-Hans. Plan B ships zh-Hans as the default language and offers an `en` toggle via the plugin's mobase `settings()`. Strings are looked up by key, not by literal text in the UI code. Future locales drop in by adding another mapping.

- [ ] **Step 1: Write the failing test**

`tests/test_localization.py`:
```python
import pytest

from Mo2AssetsInspector.localization import Locale, Strings, get_strings


def test_default_locale_is_zh_hans() -> None:
    strings = get_strings()
    assert strings.locale is Locale.ZH_HANS
    assert strings.window_title  # non-empty


def test_can_get_en_strings() -> None:
    strings = get_strings(Locale.EN)
    assert strings.locale is Locale.EN
    # The same key must exist in both locales.
    assert strings.window_title  # non-empty


@pytest.mark.parametrize("locale", list(Locale))
def test_every_locale_provides_full_string_set(locale: Locale) -> None:
    strings = get_strings(locale)
    required_attrs = [
        "window_title",
        "refresh_button",
        "section_kept",
        "section_overwritten",
        "section_no_conflict",
        "column_file",
        "column_overrider",
        "column_overridden_by",
        "column_priority",
        "column_mod_name",
        "column_conflict_count",
        "column_file_count",
        "column_archive_type",
        "rationale_header",
        "kb_reference_header",
        "unsupported_game_message",
    ]
    for attr in required_attrs:
        value = getattr(strings, attr)
        assert isinstance(value, str)
        assert value, f"Locale {locale} missing string for {attr}"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_localization.py -v
```
Expected: FAIL with "No module named 'Mo2AssetsInspector.localization'".

- [ ] **Step 3: Implement `localization.py`**

```python
"""String table for the MO2 Assets Inspector GUI.

Default locale = zh-Hans (matches the user's reference UX).
Use `get_strings()` for default, or `get_strings(Locale.EN)` to override.
The plugin's mobase `settings()` exposes the locale as a setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Locale(str, Enum):
    ZH_HANS = "zh-Hans"
    EN = "en"


@dataclass(frozen=True)
class Strings:
    locale: Locale
    window_title: str
    refresh_button: str
    section_kept: str
    section_overwritten: str
    section_no_conflict: str
    column_file: str
    column_overrider: str
    column_overridden_by: str
    column_priority: str
    column_mod_name: str
    column_conflict_count: str
    column_file_count: str
    column_archive_type: str
    rationale_header: str
    kb_reference_header: str
    unsupported_game_message: str


_ZH_HANS = Strings(
    locale=Locale.ZH_HANS,
    window_title="BGS 资源审计器",
    refresh_button="刷新",
    section_kept="冲突中被保留的文件",
    section_overwritten="冲突中被覆盖的文件",
    section_no_conflict="下列文件无冲突",
    column_file="文件",
    column_overrider="覆盖文件的来源模组",
    column_overridden_by="被覆盖的模组",
    column_priority="优先级",
    column_mod_name="模组名称",
    column_conflict_count="冲突",
    column_file_count="文件数",
    column_archive_type="来源类型",
    rationale_header="判定依据",
    kb_reference_header="知识库引用",
    unsupported_game_message=(
        "当前游戏暂未在 mo2-assets-engine 的第一阶段覆盖范围内。"
        "支持的游戏：Skyrim 系列 / Fallout 3 / Fallout NV / Fallout 4 / Starfield。"
    ),
)

_EN = Strings(
    locale=Locale.EN,
    window_title="BGS Assets Inspector",
    refresh_button="Refresh",
    section_kept="Files kept (this mod wins)",
    section_overwritten="Files overwritten (this mod loses)",
    section_no_conflict="Files with no conflict",
    column_file="File",
    column_overrider="Overrider (wins this path)",
    column_overridden_by="Overridden by",
    column_priority="Priority",
    column_mod_name="Mod name",
    column_conflict_count="Conflicts",
    column_file_count="Files",
    column_archive_type="Source",
    rationale_header="Resolution rationale",
    kb_reference_header="Knowledge-base references",
    unsupported_game_message=(
        "The active game is not in mo2-assets-engine's Phase 1 coverage. "
        "Supported: Skyrim family / Fallout 3 / Fallout NV / Fallout 4 / Starfield."
    ),
)


_STRINGS_BY_LOCALE: dict[Locale, Strings] = {Locale.ZH_HANS: _ZH_HANS, Locale.EN: _EN}


def get_strings(locale: Locale = Locale.ZH_HANS) -> Strings:
    return _STRINGS_BY_LOCALE[locale]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_localization.py -v`
Expected: 4 passed (2 individual + 2 parametrized).

- [ ] **Step 5: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector/localization.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_localization.py
git commit -m "feat(mo2-plugin): localization string table (zh-Hans default + en toggle)"
```

---

## Task 5: IPluginTool plugin shell + settings

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/plugin.py`

**Background:** The `mobase.IPluginTool` contract requires these methods: `name`, `author`, `description`, `version`, `isActive`, `settings`, `init`, `displayName`, `tooltip`, `icon`, `display`, `setParentWidget`. We need ONE setting: `locale` (string, default `"zh-Hans"`). On `display()`, we instantiate the main window (Task 6) lazily and show it non-modally. Window state is held on the plugin instance so re-clicking the Tools entry brings the existing window forward instead of opening a duplicate.

`mobase-stubs` typing: the `mobase` module is provided by MO2 at runtime; we install `mobase-stubs` for dev-time type checking but the runtime import does NOT depend on the stubs. Type-check this file with `mypy --explicit-package-bases` and add `# type: ignore[import-not-found]` to the `import mobase` line if stubs are not installed locally.

- [ ] **Step 1: Document the dev-time mobase-stubs setup**

Add to `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/__init__.py`:
```python
"""MO2 Assets Inspector support package.

Public surface for the top-level plugin entry: `plugin.create_plugin()`.

Dev-time type checking:
    pip install mobase-stubs
    mypy tools/mo2-control-plane/live-bridge/mo2_assets_inspector/ \
        --explicit-package-bases
"""
```

- [ ] **Step 2: Write `plugin.py` (no test — exercised at acceptance time inside MO2)**

```python
"""IPluginTool implementation for the BGS Assets Inspector.

Lifecycle (per https://www.modorganizer.org/python-plugins-doc/):
    1. MO2 imports the plugin module and calls `createPlugin()`.
    2. MO2 calls `init(organizer)` once with the live IOrganizer instance.
    3. When the user clicks the Tools menu entry, MO2 calls `display()`.
    4. `setParentWidget()` is called before `display()` with MO2's main window.

The window is lazily constructed on first `display()` and reused thereafter.
"""

from __future__ import annotations

from typing import Any

import mobase  # type: ignore[import-not-found]  # provided by MO2 runtime
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QWidget

from .bridge import UnsupportedGameError, bundle_paths_from_organizer
from .localization import Locale, get_strings


class BgsAssetsInspectorPlugin(mobase.IPluginTool):
    NAME = "BgsAssetsInspector"
    VERSION = mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.PRE_ALPHA)
    AUTHOR = "BB-84C"
    DESCRIPTION = (
        "Inspect loose-file + BA2/BSA archive conflicts across the active modlist "
        "with the same logic MO2's internal Conflicts tab uses, extended to cover "
        "archive contents."
    )

    def __init__(self) -> None:
        super().__init__()
        self._organizer: mobase.IOrganizer | None = None
        self._parent_widget: QWidget | None = None
        self._main_window: QWidget | None = None

    # --- IPlugin (base) -------------------------------------------------------

    def name(self) -> str:
        return self.NAME

    def author(self) -> str:
        return self.AUTHOR

    def description(self) -> str:
        return self.DESCRIPTION

    def version(self) -> mobase.VersionInfo:
        return self.VERSION

    def isActive(self) -> bool:
        if self._organizer is None:
            return False
        return bool(self._organizer.pluginSetting(self.NAME, "enabled"))

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "enabled",
                "Enable the BGS Assets Inspector tool.",
                True,
            ),
            mobase.PluginSetting(
                "locale",
                "UI locale (one of: zh-Hans, en).",
                Locale.ZH_HANS.value,
            ),
        ]

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    # --- IPluginTool ----------------------------------------------------------

    def displayName(self) -> str:
        strings = get_strings(self._locale())
        return strings.window_title

    def tooltip(self) -> str:
        return self.DESCRIPTION

    def icon(self) -> QIcon:
        return QIcon()  # placeholder; an asset icon can be added later

    def setParentWidget(self, widget: QWidget) -> None:
        self._parent_widget = widget

    def display(self) -> None:
        if self._organizer is None:
            return
        try:
            paths = bundle_paths_from_organizer(self._organizer)
        except UnsupportedGameError as exc:
            strings = get_strings(self._locale())
            QMessageBox.warning(
                self._parent_widget,
                strings.window_title,
                f"{strings.unsupported_game_message}\n\n[{exc}]",
            )
            return

        # Lazy import: the window depends on engine + Qt and we want fast plugin
        # startup. Importing here also lets us reload edits via MO2 2.4.6's
        # plugin-reload command without re-instantiating the plugin object.
        from .main_window import AssetsInspectorMainWindow

        if self._main_window is None:
            self._main_window = AssetsInspectorMainWindow(
                paths_bundle=paths,
                strings=get_strings(self._locale()),
                parent=self._parent_widget,
            )
        else:
            self._main_window.refresh(paths_bundle=paths)

        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    # --- helpers --------------------------------------------------------------

    def _locale(self) -> Locale:
        if self._organizer is None:
            return Locale.ZH_HANS
        raw = self._organizer.pluginSetting(self.NAME, "locale")
        try:
            return Locale(str(raw))
        except ValueError:
            return Locale.ZH_HANS


def create_plugin() -> BgsAssetsInspectorPlugin:
    return BgsAssetsInspectorPlugin()
```

- [ ] **Step 3: Lint + type check**

Run:
```powershell
ruff check tools/mo2-control-plane/live-bridge/mo2_assets_inspector/plugin.py
mypy tools/mo2-control-plane/live-bridge/mo2_assets_inspector/plugin.py --explicit-package-bases
```
Expected: ruff clean; mypy may warn about `import mobase` if `mobase-stubs` is not installed — the `# type: ignore` comment handles it. If `mobase-stubs` IS installed, mypy must be clean.

- [ ] **Step 4: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector/__init__.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/plugin.py
git commit -m "feat(mo2-plugin): IPluginTool plugin shell + locale setting"
```

---

## Task 6: Main window — mod list with conflict summary

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/main_window.py`
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_main_window.py` (offscreen Qt smoke)

**Background:** The main window is a `QMainWindow` with one table view that mirrors the columns from the user's screenshots: `优先级` / `模组名称` / `冲突` / `文件数` / `来源类型`. Sort by priority descending (top = highest priority = wins, matching MO2 left-pane convention). Double-click a row → open Task 7's mod detail dialog. Top toolbar carries a single `Refresh` button. The window holds an internal "world" object built by calling Plan A's engine entry points with the bundle from Task 3.

Qt tests run offscreen via `QT_QPA_PLATFORM=offscreen`; we instantiate the window and assert state without actually showing it. This catches structural regressions (column names, row counts, signal wiring) without needing a display.

- [ ] **Step 1: Write the failing offscreen Qt smoke test**

`tests/test_main_window.py`:
```python
"""Offscreen Qt smoke test for the main window.

Sets QT_QPA_PLATFORM=offscreen so we can instantiate the window in CI
without a display. We do not test pixel-level rendering — only structure
and behavior (column headers, row counts, signal emission).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from mo2_assets_engine.archive_order import Game
from Mo2AssetsInspector.bridge import PathsBundle
from Mo2AssetsInspector.localization import Locale, get_strings
from Mo2AssetsInspector.main_window import AssetsInspectorMainWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing or QApplication([])


@pytest.fixture()
def synthetic_world(tmp_path: Path) -> PathsBundle:
    profile = tmp_path / "profiles" / "Default"
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("*ModA.esp\n*ModB.esp\n", encoding="utf-8")
    mods_root = tmp_path / "mods"
    (mods_root / "ModA" / "textures").mkdir(parents=True)
    (mods_root / "ModA" / "textures" / "shared.dds").write_bytes(b"a")
    (mods_root / "ModB" / "textures").mkdir(parents=True)
    (mods_root / "ModB" / "textures" / "shared.dds").write_bytes(b"b")
    return PathsBundle(profile_dir=profile, mods_root=mods_root, game=Game.SKYRIM)


def test_main_window_lists_enabled_mods(
    qapp: QApplication, synthetic_world: PathsBundle
) -> None:
    window = AssetsInspectorMainWindow(
        paths_bundle=synthetic_world, strings=get_strings(Locale.EN)
    )
    table = window.mod_table
    assert table.rowCount() == 2
    names = sorted(table.item(r, 1).text() for r in range(table.rowCount()))
    assert names == ["ModA", "ModB"]


def test_main_window_columns_match_locale(
    qapp: QApplication, synthetic_world: PathsBundle
) -> None:
    window = AssetsInspectorMainWindow(
        paths_bundle=synthetic_world, strings=get_strings(Locale.EN)
    )
    headers = [
        window.mod_table.horizontalHeaderItem(c).text()
        for c in range(window.mod_table.columnCount())
    ]
    assert headers == [
        "Priority",
        "Mod name",
        "Conflicts",
        "Files",
        "Source",
    ]


def test_refresh_button_rebuilds_world(
    qapp: QApplication, synthetic_world: PathsBundle, tmp_path: Path
) -> None:
    window = AssetsInspectorMainWindow(
        paths_bundle=synthetic_world, strings=get_strings(Locale.EN)
    )
    # Add a new mod on disk after the window's first build.
    new_mod = synthetic_world.mods_root / "ModC"
    (new_mod / "textures").mkdir(parents=True)
    (new_mod / "textures" / "fresh.dds").write_bytes(b"c")
    modlist = synthetic_world.profile_dir / "modlist.txt"
    modlist.write_text("+ModC\n+ModA\n+ModB\n", encoding="utf-8")

    window.refresh(paths_bundle=synthetic_world)
    assert window.mod_table.rowCount() == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
$env:QT_QPA_PLATFORM = "offscreen"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_main_window.py -v
```
Expected: FAIL with "No module named 'Mo2AssetsInspector.main_window'".

- [ ] **Step 3: Implement `main_window.py`**

```python
"""Main inspector window — mod list with conflict summary.

Mirrors MO2's left-pane "Mods" view: one row per enabled mod, columns
match the user's reference screenshots (priority / name / conflicts /
files / source type). Double-click a row opens the per-mod detail dialog.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mo2_assets_engine.archive_order import (
    ArchiveLoadOrder,
    discover_archives_for_plugins,
)
from mo2_assets_engine.conflict_resolver import (
    ConflictResolver,
    resolve_all_winners,
)
from mo2_assets_engine.mod_enumerator import enumerate_mod_files
from mo2_assets_engine.profile import read_profile
from mo2_assets_engine.types import FileEntryKind

from .bridge import PathsBundle

if TYPE_CHECKING:
    from .localization import Strings


class AssetsInspectorMainWindow(QMainWindow):
    """Top-level inspector window. Holds the precomputed world state and
    exposes a refresh hook for the IPluginTool plugin to re-run on demand."""

    def __init__(
        self,
        *,
        paths_bundle: PathsBundle,
        strings: Strings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._strings = strings
        self.setWindowTitle(strings.window_title)
        self.setMinimumSize(900, 520)

        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton(strings.refresh_button, central)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)
        outer.addLayout(toolbar)

        self.mod_table = QTableWidget(0, 5, central)
        self.mod_table.setHorizontalHeaderLabels(
            [
                strings.column_priority,
                strings.column_mod_name,
                strings.column_conflict_count,
                strings.column_file_count,
                strings.column_archive_type,
            ]
        )
        self.mod_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mod_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mod_table.verticalHeader().setVisible(False)
        self.mod_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        outer.addWidget(self.mod_table)

        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.mod_table.cellDoubleClicked.connect(self._on_row_double_clicked)

        self._paths_bundle = paths_bundle
        self.refresh(paths_bundle=paths_bundle)

    # --- public --------------------------------------------------------------

    def refresh(self, *, paths_bundle: PathsBundle) -> None:
        self._paths_bundle = paths_bundle
        self._world = _build_world(paths_bundle)
        self._populate_table()

    # --- handlers ------------------------------------------------------------

    def _on_refresh_clicked(self) -> None:
        self.refresh(paths_bundle=self._paths_bundle)

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        name_item = self.mod_table.item(row, 1)
        if name_item is None:
            return
        mod_name = name_item.text()
        # Lazy import to keep first-show latency low.
        from .mod_detail_dialog import ModDetailDialog

        dialog = ModDetailDialog(
            mod_name=mod_name,
            world=self._world,
            strings=self._strings,
            parent=self,
        )
        dialog.show()

    # --- rendering -----------------------------------------------------------

    def _populate_table(self) -> None:
        rows = self._world.summary_rows()
        self.mod_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self.mod_table.setItem(index, 0, _readonly_item(str(row["priority"])))
            self.mod_table.setItem(index, 1, _readonly_item(row["name"]))
            self.mod_table.setItem(index, 2, _readonly_item(str(row["conflicts"])))
            self.mod_table.setItem(index, 3, _readonly_item(str(row["files"])))
            self.mod_table.setItem(index, 4, _readonly_item(row["source_type"]))
        # Sort by priority descending (column 0).
        self.mod_table.sortItems(0, Qt.SortOrder.DescendingOrder)


def _readonly_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class _World:
    """Precomputed engine state for a given PathsBundle.

    Built once per refresh; consumed by the main window and the per-mod
    detail dialog. Keeps the engine call graph in one place.
    """

    def __init__(self, paths_bundle: PathsBundle) -> None:
        profile = read_profile(
            profile_dir=paths_bundle.profile_dir,
            mods_root=paths_bundle.mods_root,
        )
        candidate_archives: list[str] = []
        for mod in profile.enabled_mods:
            if mod.root.exists():
                for child in mod.root.iterdir():
                    if child.is_file() and child.suffix.lower() in (".bsa", ".ba2"):
                        candidate_archives.append(child.name)
        archive_order: ArchiveLoadOrder = discover_archives_for_plugins(
            plugins=profile.enabled_plugins,
            candidate_archives=candidate_archives,
            game=paths_bundle.game,
        )
        self.profile = profile
        self.entries_by_mod = {
            mod.name: enumerate_mod_files(mod=mod, archive_order=archive_order)
            for mod in profile.enabled_mods
        }
        self.winners = resolve_all_winners(
            mods=profile.enabled_mods, entries_by_mod=self.entries_by_mod
        )
        self.resolver = ConflictResolver(
            mods=profile.enabled_mods, entries_by_mod=self.entries_by_mod
        )

    def summary_rows(self) -> list[dict]:
        rows: list[dict] = []
        for mod in self.profile.enabled_mods:
            entries = self.entries_by_mod.get(mod.name, [])
            conflicts = sum(
                1
                for e in entries
                if self.winners[e.relative_path].bucket.value != "no-conflict"
            )
            kinds = {e.kind for e in entries}
            if kinds == {FileEntryKind.LOOSE}:
                source_type = "loose"
            elif kinds == {FileEntryKind.ARCHIVED}:
                source_type = "archive"
            elif kinds == {FileEntryKind.LOOSE, FileEntryKind.ARCHIVED}:
                source_type = "mixed"
            else:
                source_type = "empty"
            rows.append(
                {
                    "priority": mod.priority,
                    "name": mod.name,
                    "conflicts": conflicts,
                    "files": len(entries),
                    "source_type": source_type,
                }
            )
        return rows


def _build_world(paths_bundle: PathsBundle) -> _World:
    return _World(paths_bundle)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
$env:QT_QPA_PLATFORM = "offscreen"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_main_window.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Lint**

Run: `ruff check tools/mo2-control-plane/live-bridge/mo2_assets_inspector/main_window.py`
Expected: clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector/main_window.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_main_window.py
git commit -m "feat(mo2-plugin): main window with mod-list summary view"
```

---

## Task 7: Mod detail dialog (3-section conflict report)

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/mod_detail_dialog.py`
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_mod_detail_dialog.py`

**Background:** Mirrors MO2's `信息 → 冲突 → 常规` tab from the user's reference screenshots. A `QDialog` with three collapsible sections (`kept` / `overwritten` / `no_conflict`). Each section is a `QTreeWidget` with the columns from the screenshots. The right-hand side of the dialog hosts the Task 8 file detail panel; clicking any row updates that panel with the resolution rationale.

- [ ] **Step 1: Write the failing offscreen smoke test**

`tests/test_mod_detail_dialog.py`:
```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from mo2_assets_engine.archive_order import Game
from Mo2AssetsInspector.bridge import PathsBundle
from Mo2AssetsInspector.localization import Locale, get_strings
from Mo2AssetsInspector.main_window import _build_world
from Mo2AssetsInspector.mod_detail_dialog import ModDetailDialog


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing or QApplication([])


@pytest.fixture()
def synthetic_world(tmp_path: Path):
    profile = tmp_path / "profiles" / "Default"
    profile.mkdir(parents=True)
    # ModA top of list → wins shared.dds; loses to nothing.
    # ModB lower → loses shared.dds to ModA; has solo-b.dds with no conflict.
    (profile / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("*ModA.esp\n*ModB.esp\n", encoding="utf-8")
    mods_root = tmp_path / "mods"
    (mods_root / "ModA" / "textures").mkdir(parents=True)
    (mods_root / "ModA" / "textures" / "shared.dds").write_bytes(b"a")
    (mods_root / "ModA" / "textures" / "solo-a.dds").write_bytes(b"a")
    (mods_root / "ModB" / "textures").mkdir(parents=True)
    (mods_root / "ModB" / "textures" / "shared.dds").write_bytes(b"b")
    (mods_root / "ModB" / "textures" / "solo-b.dds").write_bytes(b"b")
    bundle = PathsBundle(profile_dir=profile, mods_root=mods_root, game=Game.SKYRIM)
    return _build_world(bundle)


def test_dialog_for_winning_mod_lists_kept_and_no_conflict(
    qapp: QApplication, synthetic_world
) -> None:
    dialog = ModDetailDialog(
        mod_name="ModA",
        world=synthetic_world,
        strings=get_strings(Locale.EN),
    )
    assert dialog.kept_tree.topLevelItemCount() == 1
    assert dialog.kept_tree.topLevelItem(0).text(0) == "textures/shared.dds"
    assert dialog.overwritten_tree.topLevelItemCount() == 0
    assert dialog.no_conflict_tree.topLevelItemCount() == 1
    assert dialog.no_conflict_tree.topLevelItem(0).text(0) == "textures/solo-a.dds"


def test_dialog_for_losing_mod_lists_overwritten(
    qapp: QApplication, synthetic_world
) -> None:
    dialog = ModDetailDialog(
        mod_name="ModB",
        world=synthetic_world,
        strings=get_strings(Locale.EN),
    )
    assert dialog.overwritten_tree.topLevelItemCount() == 1
    overwritten = dialog.overwritten_tree.topLevelItem(0)
    assert overwritten.text(0) == "textures/shared.dds"
    # Second column = mod that wins this path.
    assert "ModA" in overwritten.text(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
$env:QT_QPA_PLATFORM = "offscreen"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_mod_detail_dialog.py -v
```
Expected: FAIL with "No module named 'Mo2AssetsInspector.mod_detail_dialog'".

- [ ] **Step 3: Implement `mod_detail_dialog.py`**

```python
"""Per-mod conflict detail dialog.

Mirrors MO2's `信息 → 冲突 → 常规` tab from the user's reference screenshots,
extended with archive-bucket entries (loose + BA2/BSA in one view).
Layout: three collapsible sections on the left, a file-detail panel on the
right showing per-entry rationale + KB citation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mo2_assets_engine.types import ConflictBucket, FileEntry, ResolvedWinner

if TYPE_CHECKING:
    from .localization import Strings
    from .main_window import _World


class ModDetailDialog(QDialog):
    def __init__(
        self,
        *,
        mod_name: str,
        world: _World,
        strings: Strings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mod_name = mod_name
        self._world = world
        self._strings = strings
        self.setWindowTitle(f"{strings.section_kept.split(' (')[0]} — {mod_name}"
                            if False else f"Conflicts — {mod_name}")
        # NB: localized window title uses generic prefix; mod name appended
        # in either locale; the dialog renders its section labels separately.
        self.resize(1100, 640)

        report = world.resolver.report_for_mod(mod_name)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        sections_widget = QWidget(splitter)
        sections_layout = QVBoxLayout(sections_widget)

        self.kept_tree = _build_winner_tree(
            title=f"{strings.section_kept} ({len(report.kept)})",
            entries=report.kept,
            kind_column_header=strings.column_overridden_by,
            strings=strings,
        )
        self.overwritten_tree = _build_winner_tree(
            title=f"{strings.section_overwritten} ({len(report.overwritten)})",
            entries=report.overwritten,
            kind_column_header=strings.column_overrider,
            strings=strings,
        )
        self.no_conflict_tree = _build_no_conflict_tree(
            title=f"{strings.section_no_conflict} ({len(report.no_conflict)})",
            entries=report.no_conflict,
            file_column_header=strings.column_file,
        )

        sections_layout.addWidget(self.kept_tree)
        sections_layout.addWidget(self.overwritten_tree)
        sections_layout.addWidget(self.no_conflict_tree)
        splitter.addWidget(sections_widget)

        # File detail panel (Task 8); lazily imported to avoid Qt cycles.
        from .file_detail_panel import FileDetailPanel

        self.detail_panel = FileDetailPanel(strings=strings, parent=splitter)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer = QHBoxLayout(self)
        outer.addWidget(splitter)

        # Wire selection → detail panel.
        for tree, picker in (
            (self.kept_tree, self._pick_kept),
            (self.overwritten_tree, self._pick_overwritten),
            (self.no_conflict_tree, self._pick_no_conflict),
        ):
            tree.itemSelectionChanged.connect(picker)

    # --- selection routing ----------------------------------------------------

    def _pick_kept(self) -> None:
        winner = _selected_winner(self.kept_tree)
        if winner is not None:
            self.detail_panel.show_winner(winner)

    def _pick_overwritten(self) -> None:
        winner = _selected_winner(self.overwritten_tree)
        if winner is not None:
            self.detail_panel.show_winner(winner)

    def _pick_no_conflict(self) -> None:
        item = self.no_conflict_tree.currentItem()
        if item is None:
            return
        self.detail_panel.show_no_conflict_path(item.text(0))


def _build_winner_tree(
    *,
    title: str,
    entries: list[ResolvedWinner],
    kind_column_header: str,
    strings: Strings,
) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels([strings.column_file, kind_column_header])
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    tree.setObjectName(title)
    for entry in entries:
        row = QTreeWidgetItem(
            [
                entry.relative_path,
                _format_other_party(entry, strings=strings),
            ]
        )
        row.setData(0, Qt.ItemDataRole.UserRole, entry)
        tree.addTopLevelItem(row)
    return tree


def _build_no_conflict_tree(
    *,
    title: str,
    entries: list[FileEntry],
    file_column_header: str,
) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels([file_column_header])
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    tree.setObjectName(title)
    for entry in entries:
        row = QTreeWidgetItem([entry.relative_path])
        tree.addTopLevelItem(row)
    return tree


def _selected_winner(tree: QTreeWidget) -> ResolvedWinner | None:
    item = tree.currentItem()
    if item is None:
        return None
    data = item.data(0, Qt.ItemDataRole.UserRole)
    if isinstance(data, ResolvedWinner):
        return data
    return None


def _format_other_party(entry: ResolvedWinner, *, strings: Strings) -> str:
    # Kept-tree → show all losers; Overwritten-tree → show the single winner.
    bucket = entry.bucket
    is_overwritten_perspective = bucket in {
        ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE,
    }
    if is_overwritten_perspective:
        return f"{entry.winner.owner_mod} [{_archive_tag(entry.winner)}]"
    # Kept perspective: list all losers.
    tags = ", ".join(
        f"{loser.owner_mod} [{_archive_tag(loser)}]" for loser in entry.losers
    )
    return tags


def _archive_tag(entry: FileEntry) -> str:
    if entry.archive is None:
        return "loose"
    return f"{entry.archive.kind.value}:{entry.archive.name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
$env:QT_QPA_PLATFORM = "offscreen"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_mod_detail_dialog.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector/mod_detail_dialog.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_mod_detail_dialog.py
git commit -m "feat(mo2-plugin): mod detail dialog (kept / overwritten / no-conflict sections)"
```

---

## Task 8: File detail panel (rationale + KB citation)

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/file_detail_panel.py`
- Create: `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_file_detail_panel.py`

**Background:** When the user clicks any entry in the mod detail dialog (Task 7), the right-hand panel updates with: the full file path, the verdict bucket, the winner + losers list, and the rationale from Task 1's `rationale_for_bucket` (short prose + KB record IDs the user can paste into `bgs_kb_get`). Read-only labels. No styling beyond Qt's default.

- [ ] **Step 1: Write the failing offscreen smoke test**

`tests/test_file_detail_panel.py`:
```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from mo2_assets_engine.types import (
    ArchiveEntry,
    ArchiveKind,
    ConflictBucket,
    FileEntry,
    FileEntryKind,
    ResolvedWinner,
)
from Mo2AssetsInspector.file_detail_panel import FileDetailPanel
from Mo2AssetsInspector.localization import Locale, get_strings


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing or QApplication([])


def test_show_winner_renders_bucket_winner_and_kb_id(qapp: QApplication) -> None:
    panel = FileDetailPanel(strings=get_strings(Locale.EN))
    winner = ResolvedWinner(
        relative_path="textures/foo.dds",
        winner=FileEntry(
            relative_path="textures/foo.dds",
            kind=FileEntryKind.LOOSE,
            owner_mod="WinnerMod",
            archive=None,
        ),
        losers=[
            FileEntry(
                relative_path="textures/foo.dds",
                kind=FileEntryKind.ARCHIVED,
                owner_mod="LoserMod",
                archive=ArchiveEntry(
                    name="LoserMod - Main.ba2",
                    kind=ArchiveKind.BA2_GENERAL,
                    load_order=0,
                ),
            )
        ],
        bucket=ConflictBucket.LOOSE_OVERWRITES_ARCHIVE,
    )
    panel.show_winner(winner)
    body = panel.body_text()
    assert "textures/foo.dds" in body
    assert "WinnerMod" in body
    assert "LoserMod" in body
    assert "loose-overwrites-archive" in body
    assert "archive-precedence.loose-over-archive.v1" in body


def test_show_no_conflict_path_renders_minimal_summary(qapp: QApplication) -> None:
    panel = FileDetailPanel(strings=get_strings(Locale.EN))
    panel.show_no_conflict_path("textures/solo.dds")
    body = panel.body_text()
    assert "textures/solo.dds" in body
    assert "no-conflict" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
$env:QT_QPA_PLATFORM = "offscreen"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_file_detail_panel.py -v
```
Expected: FAIL with "No module named 'Mo2AssetsInspector.file_detail_panel'".

- [ ] **Step 3: Implement `file_detail_panel.py`**

```python
"""Right-hand file detail panel.

Renders the full resolution rationale + KB citation for one selected entry.
The body is a plain QTextBrowser (read-only, supports rich text and clickable
KB IDs once a future hook wires `bgs_kb_get` clicks).
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from mo2_assets_engine.rationale import rationale_for_bucket
from mo2_assets_engine.types import ConflictBucket, FileEntry, ResolvedWinner

if TYPE_CHECKING:
    from .localization import Strings


class FileDetailPanel(QWidget):
    def __init__(self, *, strings: Strings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._strings = strings
        layout = QVBoxLayout(self)
        self._browser = QTextBrowser(self)
        self._browser.setOpenExternalLinks(False)
        layout.addWidget(self._browser)

    def body_text(self) -> str:
        return self._browser.toPlainText()

    def show_winner(self, winner: ResolvedWinner) -> None:
        rationale = rationale_for_bucket(winner.bucket)
        winner_tag = _archive_tag(winner.winner)
        loser_lines = "\n".join(
            f"  - {escape(loser.owner_mod)} [{_archive_tag(loser)}]"
            for loser in winner.losers
        )
        body = (
            f"Path: {winner.relative_path}\n"
            f"Bucket: {winner.bucket.value}\n"
            f"\n"
            f"Winner: {winner.winner.owner_mod} [{winner_tag}]\n"
            f"Losers:\n{loser_lines or '  (none)'}\n"
            f"\n"
            f"{self._strings.rationale_header}:\n{rationale.short}\n"
            f"\n"
            f"{self._strings.kb_reference_header}:\n"
            + "\n".join(f"  - {rid}" for rid in rationale.kb_record_ids)
        )
        self._browser.setPlainText(body)

    def show_no_conflict_path(self, path: str) -> None:
        rationale = rationale_for_bucket(ConflictBucket.NO_CONFLICT)
        body = (
            f"Path: {path}\n"
            f"Bucket: {ConflictBucket.NO_CONFLICT.value}\n"
            f"\n"
            f"{self._strings.rationale_header}:\n{rationale.short}\n"
            f"\n"
            f"{self._strings.kb_reference_header}:\n"
            + "\n".join(f"  - {rid}" for rid in rationale.kb_record_ids)
        )
        self._browser.setPlainText(body)


def _archive_tag(entry: FileEntry) -> str:
    if entry.archive is None:
        return "loose"
    return f"{entry.archive.kind.value}:{entry.archive.name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
$env:PYTHONPATH = "tools\mo2-control-plane\live-bridge;tools\mo2-assets-engine\src"
$env:QT_QPA_PLATFORM = "offscreen"
pytest tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_file_detail_panel.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Lint full plugin tree**

Run:
```powershell
ruff check tools/mo2-control-plane/live-bridge/mo2_assets_inspector/
```
Expected: clean.

- [ ] **Step 6: Commit**

```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector/file_detail_panel.py tools/mo2-control-plane/live-bridge/mo2_assets_inspector/tests/test_file_detail_panel.py
git commit -m "feat(mo2-plugin): file detail panel with rationale + KB citation"
```

---

## Task 9: Acceptance against `.artifacts/mo2` harness (live MO2)

**Files:**
- Create: `.opencode/artifacts/mo2-assets-inspector/acceptance/gui-vs-cli/README.md` (evidence dir)
- Modify: `docs/internal/roadmap.md` (Plan B shipped row + Current Focus update)

**Background:** Plan B's acceptance is the live-MO2 cross-check. The plugin and the Plan A CLI must agree on every loose-file verdict against a real mod in the harness. The GUI is also visually compared to MO2's own Conflicts tab. Three semantic gates: (a) plugin loads in MO2 without errors, (b) GUI verdict ↔ CLI verdict agreement on the loose slice, (c) GUI verdict ↔ MO2's own Conflicts tab agreement on the loose slice. Archive-bucket entries are gated only on (a) and (b) — no (c) cross-check exists.

PREREQUISITE: MO2 is closed before deployment, then started normally. Plan A's CLI is installed (`pip install -e tools/mo2-assets-engine[dev]`).

- [ ] **Step 1: Close MO2 if running, then deploy the plugin**

```powershell
# Confirm MO2 is not running. If it is, close it via its own UI; do not kill.
$env:BGS_MO2_ROOT = "D:\awesome-bgs-mod-master\.artifacts\mo2"
pwsh scripts/deploy-mo2-assets-inspector.ps1
```

Verify the deployed tree:
```powershell
Get-ChildItem "$env:BGS_MO2_ROOT\plugins\mo2_assets_inspector.py"
Get-ChildItem "$env:BGS_MO2_ROOT\plugins\Mo2AssetsInspector\" -Recurse | Select-Object FullName -First 20
Test-Path "$env:BGS_MO2_ROOT\plugins\Mo2AssetsInspector\vendored\mo2_assets_engine\__init__.py"
```

- [ ] **Step 2: Launch MO2 with the visible entrypoint**

Per the project memory `40-mo2-launcher-architecture.md`:
```powershell
Start-Process 'D:\awesome-bgs-mod-master\.artifacts\mo2\ModOrganizer.exe' `
    -ArgumentList @('-p', 'Default')
```

Verify in MO2: `Tools` menu lists `BGS 资源审计器` (zh-Hans default) or `BGS Assets Inspector` (en). Plugin name `BgsAssetsInspector` appears in `Settings → Plugins`.

If the plugin fails to appear: check `<MO2_Root>\logs\` and `<MO2_Root>\plugins\plugin_python.log` for the import error. Most common failure modes: (a) `mobase` API mismatch (different MO2 version), (b) PyQt5 vs PyQt6 mismatch, (c) `sys.path` insert not picking up the vendored engine.

- [ ] **Step 3: Open the plugin window and verify mod list**

In MO2:
1. Click `Tools → BGS 资源审计器` (or English title if locale was switched).
2. Window opens; mod list populates within ~5 seconds for the small harness.
3. Visual checks: priority column descending, mod names match MO2's left pane, conflicts/files columns non-zero for mods that actually have files.

Compare against MO2's left pane (visible behind the plugin window). The mod order should match.

- [ ] **Step 4: GUI vs CLI agreement check (loose slice)**

Pick one mod with known loose-file conflicts from the harness. Run the CLI:
```powershell
mo2-assets mod-conflicts "<MOD_NAME>" `
  --profile "$env:BGS_MO2_ROOT\profiles\Default" `
  --mods "$env:BGS_MO2_ROOT\mods" `
  --game fallout4 `
  --format json `
  | Out-File -FilePath ".opencode\artifacts\mo2-assets-inspector\acceptance\gui-vs-cli\cli-<MOD_NAME>.json" -Encoding utf8
```

In the plugin GUI, double-click the same mod. For each loose path in the dialog's `冲突中被保留的文件` and `冲突中被覆盖的文件` sections, verify it appears in the CLI JSON under `kept[].path` or `overwritten[].path` respectively. Note ANY divergence.

- [ ] **Step 5: GUI vs MO2 built-in Conflicts tab agreement (loose slice only)**

For the same mod:
1. Right-click → `信息 → 冲突 → 常规` in MO2.
2. For each entry in MO2's `冲突中被保留的文件`, verify the same loose path appears in the plugin GUI's same section.
3. Same for `冲突中被覆盖的文件`.
4. ARCHIVE entries in the plugin GUI are expected to be ABSENT from MO2's built-in tab — that is the gap this plugin fills; do not treat as divergence.

Take a screenshot of MO2's built-in dialog and a screenshot of the plugin dialog showing the same mod. Save both under `.opencode/artifacts/mo2-assets-inspector/acceptance/gui-vs-cli/`.

- [ ] **Step 6: Write the acceptance README**

`.opencode/artifacts/mo2-assets-inspector/acceptance/gui-vs-cli/README.md`:
```markdown
# Plan B acceptance — GUI ↔ CLI ↔ MO2 cross-check

Date: <YYYY-MM-DD>
Harness: D:\awesome-bgs-mod-master\.artifacts\mo2 (FO4 profile Default)
Plugin version: <BgsAssetsInspectorPlugin.VERSION>
Engine version: mo2-assets-engine 0.1.0-dev0

## Mod under test

<MOD_NAME>

## Gates

| Gate | Verdict | Notes |
|---|---|---|
| (a) Plugin loads in MO2 without errors | PASS / FAIL | <screenshot path / log snippet> |
| (b) GUI vs CLI agreement on loose slice | PASS / FAIL | <count of agreeing entries> |
| (c) GUI vs MO2 built-in Conflicts tab on loose slice | PASS / FAIL | <count of agreeing entries> |

## Archive-bucket entries (no MO2 cross-check, gated only on (a) + (b))

<count of archive entries surfaced by GUI / CLI; sample 3 of them>

## Divergences found

<list of any disagreement with root-cause note>

## Files

- cli-<MOD_NAME>.json
- gui-screenshot.png
- mo2-builtin-screenshot.png
```

- [ ] **Step 7: Update roadmap**

In `docs/internal/roadmap.md`, replace the previous Plan-A-only Current Focus item with:

```markdown
1. **Archive / loose-file reasoning helpers — Plan A + Plan B both shipped 2026-MM-DD.** `tools/mo2-assets-engine/` provides a Python engine + `mo2-assets` CLI; `tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py` provides an in-MO2 `IPluginTool` GUI mirroring MO2's Conflicts tab and extending it with BA2/BSA archive contents. Both surfaces share the same engine. Coverage: FO4 vanilla BA2 (GNRL+DX10), Skyrim LE/SE/AE/VR BSA v104/v105, FO3/FNV BSA v104, Starfield BA2 v2/v3. Semantic acceptance evidence under `.opencode/artifacts/mo2-assets-engine/acceptance/` and `.opencode/artifacts/mo2-assets-inspector/acceptance/`. FO4 next-gen v7/v8, INI `SArchiveList`, and the unified MO2 MCP that subsumes both surfaces are deferred to future phases.
```

Update the Capability Map row added in Plan A to reflect both surfaces:
```markdown
| archive/loose-file reasoning helpers | Shipped (Plan A + B 2026-MM-DD) | `tools/mo2-assets-engine/` (CLI) + `tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py` (MO2 IPluginTool GUI). Single shared engine; both surfaces agree on every verdict. FO4 next-gen BA2 + INI SArchiveList deferred. |
```

- [ ] **Step 8: Materialize portable plugin + two-commit shape**

Per `AGENTS.md` 2026-06-03:
```powershell
pwsh scripts/build-portable-plugin.ps1 -OutputDir plugins -PluginName bgs-modding-superpowers -McpPathStrategy relative -Force
```

Confirm the portable tree now carries the inspector support tree and the deploy script. The materializer should pick up `tools/mo2-control-plane/live-bridge/mo2_assets_inspector/` and `tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py` since it already mirrors the live-bridge dir. If the deploy script is NOT yet in the materializer's `scripts/` mirror list, add it.

Commit 1 (source + acceptance):
```powershell
git add tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py `
        tools/mo2-control-plane/live-bridge/mo2_assets_inspector/ `
        scripts/deploy-mo2-assets-inspector.ps1 `
        .opencode/artifacts/mo2-assets-inspector/ `
        docs/internal/roadmap.md
git commit -m "feat(mo2-plugin): mo2_assets_inspector IPluginTool GUI (Plan B) + acceptance"
```

Commit 2 (materialized):
```powershell
git add plugins/bgs-modding-superpowers/
git commit -m "chore(plugin): materialize mo2_assets_inspector into portable tree"
```

- [ ] **Step 9: Push + refresh vendor clone**

```powershell
git push origin main
git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' pull --ff-only origin main
git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' log --oneline -5
```

Verify the vendor clone reflects both Plan A and Plan B commits. Grep for `BgsAssetsInspectorPlugin` in the vendor tree to confirm the materialized plugin landed.

---

## Self-Review

**1. Spec coverage check.** Every load-bearing item from the bundled proposal maps to a task:

| Spec item | Task |
|---|---|
| IPluginTool window inside MO2 (1(a) gate) | Task 5 + Task 6 |
| Progressive disclosure: mod summary → 3-section drill → file detail | Task 6 → Task 7 → Task 8 |
| Mirror MO2's existing Conflicts tab layout (kept / overwritten / no-conflict) | Task 7 |
| Extend MO2's UX to include archive contents | Tasks 6-8 (archive tag rendered alongside loose) |
| zh-Hans default + en toggle (per screenshot reference) | Task 4 (locale) + Task 5 (settings hook) |
| New IPluginTool plugin file (4(a) gate) | Task 2 (file shell) + Task 5 (plugin class) |
| Single shared engine with the CLI | Task 3 (bridge feeds engine entry points) + Task 6 (`_World` calls engine) |
| KB citation in rationale | Task 1 (rationale module) + Task 8 (panel render) |
| Acceptance against `.artifacts/mo2` harness | Task 9 (gates a/b/c) |
| Materialization + vendor pull per AGENTS.md | Task 9 Step 8-9 |
| Plan A is hard dependency | Header + Task 2 (vendored engine copy) + every test's `PYTHONPATH` |
| FO4 next-gen / INI / unified MCP OUT of scope | Header "Out of scope" section + Task 9 Step 7 (roadmap) |

**2. Placeholder scan.** Searched for "TBD", "TODO", "implement later", "add appropriate", "handle edge cases", "similar to Task". None found in task bodies. Task 9 carries `2026-MM-DD` and `<MOD_NAME>` placeholders that the executor fills at completion time — this is intentional (the date and the chosen test mod are unknown until the task actually runs).

**3. Type consistency.** Spot-checked symbol consistency:
- `PathsBundle`, `bundle_paths_from_organizer(organizer)`, `UnsupportedGameError` — defined Task 3, consumed Task 5 (`display()`) and Task 6 (`_World.__init__`).
- `Locale`, `Strings`, `get_strings(locale)` — defined Task 4, consumed Task 5 + 6 + 7 + 8.
- `_World`, `_World.summary_rows()`, `_World.resolver`, `_World.winners` — defined Task 6, consumed Task 7 (`ModDetailDialog.__init__`).
- `AssetsInspectorMainWindow.refresh(paths_bundle=)`, `AssetsInspectorMainWindow.mod_table` — defined Task 6, consumed Task 5 (`display()`).
- `ModDetailDialog.kept_tree` / `.overwritten_tree` / `.no_conflict_tree` — defined Task 7, used by Task 7's tests.
- `FileDetailPanel.show_winner(winner)` / `.show_no_conflict_path(path)` / `.body_text()` — defined Task 8, consumed Task 7 (selection routing) and Task 8's tests.
- `rationale_for_bucket(bucket)` / `BucketRationale.short` / `.kb_record_ids` — defined Task 1, consumed Task 8.

**4. Known minor risks (called out, not blockers).**
- `mobase.IOrganizer.profilePath()` and `modsPath()` return strings on current MO2 builds; `mobase-stubs` confirms the return type, but the live MO2 process may have a slightly different shape on older Python proxy versions. Task 9 Step 2's failure-mode triage already covers this.
- The `mobase.VersionInfo` constructor signature changed across MO2 versions. The plugin uses `mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.PRE_ALPHA)` which matches the current `mobase-stubs` shape (per https://www.modorganizer.org/python-plugins-doc/). If the live MO2 rejects it, the fallback is `mobase.VersionInfo("0.1.0-alpha")` — known shape in older builds. Triage in Task 9.
- PyQt6 vs PyQt5: current MO2 ships Qt6, so `from PyQt6 import ...` is correct. If a contributor's local MO2 is an older Qt5 build, the plugin will fail to load; the fix is to upgrade MO2, not to backport. Task 9's failure-mode notes already mention this.
- Window-title localization in the mod detail dialog uses a partial-string slice trick that's fragile. The current code falls back to a hard-coded English prefix `"Conflicts — "` regardless of locale — a known stylistic blemish to clean up in a follow-up.

---

## Coordination With Plan A

- Plan A and Plan B can be authored in parallel sessions; tests pass independently for the most part.
- Plan A Task 9 (CLI) must be GREEN before Plan B Task 9 (acceptance) can run end-to-end — the GUI cross-checks against the CLI.
- The shared engine package (`tools/mo2-assets-engine/`) is owned conceptually by Plan A, but Plan B Task 1 adds the `rationale.py` module — this is additive and does not retroactively change Plan A.
- For commit-cycle discipline: Plan A's branch lands first (engine + CLI + Plan A acceptance), Plan B's branch lands second on top (rationale + IPluginTool + Plan B acceptance). Recommended branch names: `feat/plan-a-mo2-assets-engine-and-cli` then `feat/plan-b-mo2-assets-inspector-gui`.
- If executing both in one session with a single best-of-N orchestration, run Plan A Tasks 1-9 sequentially first, then Plan B Tasks 1-9; do not interleave because Plan B Task 5+ imports the engine package built by Plan A.

---

## Execution Handoff

Plan complete and saved to `docs/internal/plans/2026-06-13-mo2-assets-inspector-ipluginthool-gui.md`. Two execution options (same shape as Plan A):

**1. Subagent-Driven (recommended)** — Fresh `@laborer` / `@fixer` per task, review between tasks. Qt offscreen tests catch most structural regressions early; the live MO2 acceptance gate at Task 9 is the irreducible human-in-the-loop step.

**2. Inline Execution** — Tasks run in this session with checkpoints. Lower setup overhead but higher context cost than subagent-driven.

Which approach (and run Plan A + Plan B as one combined execution track, or separate branches)?
