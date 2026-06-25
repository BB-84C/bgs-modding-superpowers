---
id: engine.xse-update-workflow.v1
title: Script Extender (xSE) update workflow — game-root drop, runtime-pinned dll
kind: rule
domains: [engine, install-planning]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Script Extenders (SKSE/F4SE/NVSE/SFSE) live in the game install root next to the .exe (NOT in MO2 mods/ overlay), and ship as a versioned .7z archive containing `<xse>_loader.exe` + `<xse>_<runtime_version>.dll` + readme + whatsnew + source archive. Updates must match the current Steam game runtime exactly; replace requires backup-before-replace + sha256 verify; the 7z extracts to a versioned SUBDIRECTORY (e.g. `sfse_0_2_21/`), not flat — always glob-find the actual files after extract."
  confidence: high
queryKeys: [SFSE, SKSE, F4SE, NVSE, script extender, xSE update, game root, sfse_loader, sfse dll, runtime version mismatch, cascade, Address Library, SFSE Plugin Loader dialog, address library needs to be updated, incompatible with current version, Data/ prefix, archive structure, flatten, mod folder layout]
severity: high
sources:
  - kind: official
    url: "https://sfse.silverlock.org/"
    ref: "SFSE official site (silverlock points to Nexus mod #106 for distribution)"
  - kind: official
    url: "https://skse.silverlock.org/"
    ref: "SKSE official site"
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: "F4SE official site"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Script Extender (xSE) update workflow — game-root drop, runtime-pinned dll

Script Extenders such as SKSE, F4SE, NVSE, FOSE, and SFSE are game-root tools, not MO2 Data overlays. The loader must sit next to the game executable so it can start the real game process and inject the matching runtime DLL. MO2's VFS projects `Data/` content; it does not safely replace the game root executable neighborhood.

Runtime pinning is the containment seal. The extender DLL filename encodes the supported runtime, such as `sfse_1_16_244.dll` or an SKSE64 build tied to a specific Skyrim runtime. If Steam updates the game overnight, yesterday's matching extender can fail the next morning. The usual symptom is that launching through the extender loader no longer starts the game or exits immediately. Verify the current `<game>.exe` `FileVersion` against the extender's supported runtime before replacing files.

Official archives are usually versioned `.7z` files that extract into a versioned subdirectory, not a flat staging directory. Scripts must find the real files after extraction rather than assuming fixed relative paths:

```powershell
$dll = Get-ChildItem $stagingDir -Recurse -Filter "sfse_*.dll" | Select-Object -First 1
$loader = Get-ChildItem $stagingDir -Recurse -Filter "sfse_loader.exe" | Select-Object -First 1
```

## Archive structure flatten — the `Data/` prefix gotcha

Nexus archives come in two top-level layouts:

- **Flat** (most common, MO2-standard): archive contents at top level — e.g. `SFSE/Plugins/<dll>`, `interface/*.swf`. Extracting directly into an MO2 mod folder places files at correct paths (since MO2 mod folder root maps to game `Data/` via VFS).
- **Data-prefixed** (less common but real): archive contents nested under top-level `Data/` — e.g. `Data/SFSE/Plugins/<dll>`. If extracted naively into an MO2 mod folder, files end up at `<modDir>/Data/SFSE/Plugins/<dll>` which MO2's VFS would map to in-game `Data/Data/SFSE/Plugins/<dll>` — wrong.

The fix is to flatten before installing:

```powershell
$dataSubdir = "$modDir\Data"
if (Test-Path -LiteralPath $dataSubdir) {
  Get-ChildItem -LiteralPath $dataSubdir | ForEach-Object {
    $dst = Join-Path $modDir $_.Name
    if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Recurse -Force }
    Move-Item -LiteralPath $_.FullName -Destination $modDir -Force
  }
  Remove-Item -LiteralPath $dataSubdir -Recurse -Force
}
```

Important: when REPLACING an existing mod folder's contents (e.g. update workflow), the OLD files at non-Data-prefixed paths must be removed BEFORE moving the new `Data/`-prefixed files up — otherwise the move overwrites the right files into the right places, but leaves stale unrelated files at the old paths. The cleanest pattern is:

1. Extract archive to staging dir.
2. If staging top-level has `Data/`, treat staging's `Data/` as the actual source root.
3. For each top-level child in source root: if same-name child exists in mod folder, delete it first, then copy/move from source.

Real case: BB84 CharGenMenu update 2026-06-24, v1.1.0.20 archive was flat (`SFSE/...`, `interface/...`) but v1.1.0.22 archive ships with `Data/` prefix. Naive overlay-copy created duplicated files at two paths until cleanup was applied.

This applies to ALL Nexus mod updates, not just xSE plugins — same gotcha shows up in BSA/BA2 archive overhauls, mesh/texture replacements, and FOMOD-flattened install variants.

The standard update workflow is: detect the current extender by the `<xse>_*.dll` file in the game root; check the official page or distribution page for the latest supported runtime; if the Steam runtime advanced, download the matching `.7z`; extract to staging; back up current game-root extender files (`<xse>_loader.exe`, `<xse>_<oldver>.dll`, `<xse>_readme.txt`, `<xse>_whatsnew.txt`); copy the new files; replace readme and whatsnew; optionally delete the old runtime DLL for cleanliness; then verify SHA256 for all copied files.

## Cascade pattern: xSE → Address Library → SFSE/SKSE/F4SE plugin mods

A game runtime update does NOT stop at xSE. It cascades:

1. **xSE binary** (`sfse_loader.exe` + `sfse_<runtime>.dll`) — drops into the
   game root next to `<game>.exe`. Only this layer touches the actual game
   install. Covered earlier in this record.
2. **Address Library** — a normal MO2 mod containing `Data\SFSE\Plugins\versionlib-<runtime>.bin` files.
   When the game runtime bumps, the bundled `versionlib-<old-runtime>.bin` becomes irrelevant; the new
   `versionlib-<new-runtime>.bin` must be present. Update via standard Nexus
   workflow (#3256 for Starfield), DOES NOT touch game root — the .bin
   files live under the mod's `SFSE\Plugins\` directory and MO2's VFS
   projects them into `Data\SFSE\Plugins\`.
3. **Every SFSE/SKSE/F4SE plugin mod** — each one ships its own
   `Data\SFSE\Plugins\<plugin>.dll`. Two failure classes:
   - `<plugin>.dll vN.N.N: disabled, address library needs to be updated` —
     mod itself is fine, just needs the new Address Library .bin (Step 2
     above fixes it).
   - `<plugin>.dll vN.N.N: disabled, incompatible with current version of
     the game` — mod needs its own version bump from the author. Check
     Nexus for a newer version; if `status=not_published` or `status=hidden`
     the author has pulled the mod and the user must decide (disable / find
     replacement / accept loss).

The `SFSE Plugin Loader` dialog at game launch (after SFSE itself succeeds)
lists every mod that failed for each of these reasons. That dialog is the
canonical user-facing diagnostic for the cascade state.

For a full cascade workflow:

1. Update SFSE binary in game root (see earlier section). Launch game once
   to surface the SFSE Plugin Loader's mod-failure dialog.
2. Update Address Library to the latest version (Nexus mod page lists the
   target runtime in the filename, e.g. "All in one - v22 (1.16.244.0)").
   This fixes every mod whose dialog message was "address library needs to
   be updated".
3. For each mod whose dialog message was "incompatible with current version
   of the game", check Nexus for a newer version:
   - If newer published version exists: update the mod (Premium download
     via `/v1/games/{game}/mods/{id}/files/{file_id}/download_link.json`,
     extract, replace MO2 mod folder contents, update meta.ini).
   - If `status=not_published` or `status=hidden`: report to user; the agent
     cannot decide whether to disable, find replacement, or wait.
4. Launch game again to verify the SFSE Plugin Loader dialog is empty.

**Placeholder dummy mod convention (BB84 personal, optional):** Some
curators keep an empty MOD folder under `<MO2Root>/mods/<XSE Name>
<runtime-tag>/` (e.g. `Starfield Script Extender 1-15-222/`) with a single
`sfse_<binary-ver>/` empty subdir + a complete `meta.ini` carrying the
real `modid=106` + `version=` + `installationFile=` + nexus-side metadata.
This makes the xSE binary version VISIBLE in MO2's mod list (since the
real binary lives outside MO2's VFS and is otherwise invisible to MO2's
update-tracking). Rename folder on each xSE update. **This is a curator
convention, not a universal rule.**

[CAUTION] This workflow writes directly to the real game install root. It requires explicit user confirmation in the current session, a backup-before-replace step, and a final readback. Vault-Tec is not responsible for unexpected Steam auto-updates, loader mismatch radiation leaks, or Chryslus-fueled file drift.
