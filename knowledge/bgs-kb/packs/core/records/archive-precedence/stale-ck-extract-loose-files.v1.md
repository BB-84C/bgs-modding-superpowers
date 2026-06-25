---
id: archive-precedence.stale-ck-extract-loose-files.v1
title: Stale Creation Kit loose extracts silently shadow runtime BA2 archives across patches
kind: gotcha
domains: [archive-precedence, install-planning, debugging]
appliesTo:
  games: [SkyrimSE, SkyrimAE, Fallout4, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: When archive invalidation is enabled on a BGS install that also has the Creation Kit, loose files extracted by CK into `Data\` can silently shadow runtime BA2 archives. Across a game patch boundary, those extracts become stale — same filenames, valid-at-extract-time content, but referencing shaders/textures/scripts that no longer match the new compiled databases. The loose-overrides-archive rule then locks in a broken render path. Recovery is to delete the stale CK extract trees; the runtime BA2 takes over, and `Tools\ContentResources.zip` re-extracts a patch-matched copy whenever CK editing is actually needed.
  confidence: high
queryKeys:
  - stale loose files
  - CK extract
  - ContentResources.zip
  - archive invalidation
  - loose overrides archive
  - missing textures after game update
  - purple terrain after patch
  - materials.ba2 shadow
  - particles broken
  - post-patch hygiene
  - Data Materials delete
  - Data Particles delete
severity: high
sources:
  - kind: tooling-docs
    ref: Starfield Geometry Bridge — `.mat` file documentation (BA2 archives don't contain loose `.mat`, but do contain a compiled material database)
    url: https://starfieldgeometrybridge.github.io/docs/tips/material/
  - kind: tooling-docs
    ref: hst12/Starfield-Creations-Mod-Manager-and-Catalog-Fixer — "Delete Loose File Folders" feature deletes materials/particles/scripts/textures-subfolders as a recognized cleanup
    url: https://github.com/hst12/Starfield-Creations-Mod-Manager-and-Catalog-Fixer
  - kind: tooling-docs
    ref: CK Papyrus Compiler command files — documents `Data\Scripts\Source\Base` as the canonical extraction target from ContentResources.zip
    url: https://www.nexusmods.com/starfield/mods/10320
  - kind: project-internal-doc
    ref: BB84 2026-06-25 post-1.16.244 purple-terrain incident — Materials delete alone resolved the visual breakage on a 245-mod profile
related:
  - archive-precedence.loose-over-archive.v1
  - install-planning.script-extender-version-matrix.v1
  - engine.xse-update-workflow.v1
  - install-planning.mod-update-post-state-discipline.v1
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# Stale Creation Kit loose extracts silently shadow runtime BA2 archives across patches

## Perspective: OBJECTIVE

The loose-overrides-archive rule is the foundation of BGS modding — it is also what makes Creation Kit's auto-extract behavior dangerous across game patches.

## The mechanism — three layers stacking the trap

A modern Bethesda game ships its compiled assets in BA2 archives. For Starfield specifically: `Starfield - Materials.ba2` holds a compiled material database (`.cdb`); `Starfield - Particles.ba2` holds compiled particle definitions; `Starfield - Misc.ba2` holds compiled `.pex` Papyrus scripts. The runtime reads from those archives by default.

The Creation Kit installs alongside the game and extracts its authoring-time inputs from `Tools\ContentResources.zip` — typically into `Data\Materials\` (`.mat` JSON files), `Data\Particles\` (`.psfx`, `.pefx`), `Data\Scripts\Source\` (`.psc` source), plus editor-only metadata under `Data\DataViews\`, `Data\EditorFiles\`. The extracts can be tens of thousands of files and hundreds of megabytes; for Starfield CK the Materials extract alone is roughly 50,000 files.

Archive invalidation, which any modded curator has enabled via `StarfieldCustom.ini` `[Archive] bInvalidateOlderFiles=1 + sResourceDataDirsFinal=`, makes loose files in `Data\` override BA2 contents. This is the feature that lets mods replace base game assets without repacking BA2.

Stack the three layers: the curator's runtime now reads CK-extracted authoring files instead of the patched BA2 database. While the game version matches the CK extract version, this is invisible — the loose files describe the same materials as the BA2, just unpacked. The day the game patches the material database, particle archive, or compiled scripts is the day the silent shadow becomes visible breakage. The loose files now reference textures that no longer exist, parameters that have changed meaning, or shader paths that have been refactored. The trap engages.

## The signature

The classic signature is "after a recent game update, something visual or behavioral broke in a modded profile that was previously stable". Common visible forms:

- Purple/iridescent terrain or surfaces — material definitions reference shaders or textures the patched runtime no longer ships
- Missing meshes or floating partial geometry — material swap landing on a removed asset path
- Wrong particle effects, invisible or oversized VFX — particle definitions out of sync with compiled archive
- Subtle Papyrus regressions in base game scripts — loose `.pex` overriding patched `Starfield - Misc.ba2` (this is rarer because `.psc` source is not loaded by runtime, but tooling that compiles and drops `.pex` into `Data\Scripts\` produces the same trap)

The trap is hostile to standard diagnostic reflexes:

- The loose files look right. Same names, same paths, same JSON structure. There is no error message saying "this file is too old".
- The mod overlay is the first suspect. Curators assume the heavy-modded profile is the problem and start preparing to bisect the mod set.
- An empty test profile may render fine if the curator did not actually walk to the affected scene, generating a false asymmetric-evidence signal that misdirects investigation away from the simple cause.

## The diagnostic ladder

Before bisecting mods or rolling back the game version:

1. Compare against a near-empty profile and **actually go to the same in-game location with the same lighting state** (per `debugging.asymmetric-evidence-self-falsify.v1`). The empty-profile baseline (`diagnosing-bgs-problems`) is only valid if the comparison was actually made.
2. List `Data\` top-level subdirectories whose names match BGS asset paths: `Materials`, `Particles`, `Scripts`, `Textures`, `Meshes`, `Sound`, `Interface`, `Geometries`. Any of those that exist with file modification times **older than the current patch's BA2 modification times** are stale CK extracts.
3. Cross-check `Tools\ContentResources.zip`. Its modification time should match the current patch. If yes, the recovery path is intact — any deletion is reversible by re-extracting.
4. Cross-check `StarfieldCustom.ini` `[Archive]` lines. If `bInvalidateOlderFiles=1` and `sResourceDataDirsFinal=` (empty value) are present, archive invalidation is enabled and stale loose files are actively shadowing. (This is the normal modded-curator state.)

## The fix

Delete the stale extract trees from the game-install `Data\`. The compiled databases in BA2 form take over immediately. Cleanup priorities for Starfield, from highest runtime impact to lowest:

- `Data\Materials\` — runtime; `.mat` shadows `Starfield - Materials.ba2`
- `Data\Particles\` — runtime; `.psfx` shadows `Starfield - Particles.ba2`
- `Data\Textures\` — runtime if any `.dds` paths collide
- `Data\Scripts\` — runtime if any `.pex` were compiled into here (CK Papyrus compiler default output target)
- `Data\Source\`, `Data\DataViews\`, `Data\EditorFiles\` — CK-editor-only, safe to delete (not loaded by runtime)

The recovery path is `Tools\ContentResources.zip`. When the curator next wants to use the CK, extract it to `Data\` for a fresh, patch-matched copy. A cleaner habit is to extract `ContentResources.zip` into a dedicated Mod Organizer 2 mod folder (e.g. `mods/CK Resources Vanilla/`) so the loose files can be toggled on/off without touching the real game install.

## Cross-patch hygiene as a discipline

The clean shape for long-term modded curators is:

- Treat CK loose extracts as belonging to a single game version. After every game patch, decide whether to refresh them (re-extract from current `ContentResources.zip`) or to remove them until the next CK session needs them.
- Inspect the game-install `Data\` for stale extracts as part of every post-patch maintenance pass, alongside the standard xSE / Address Library cascade work documented in `engine.xse-update-workflow.v1`.
- Never assume the absence of an error message means the loose extracts are matching the runtime. The silent-shadow failure mode is the rule, not the exception.

## Cross-game scope

The pattern is most aggressive on Starfield because Creation Engine 2 introduced the compiled material database model — `.mat` files are a new artifact class, and the CK extracts them at scale. Skyrim SE and Fallout 4 CKs produce less aggressive auto-extracts because their material model embeds shader properties directly in NIF files, but loose `.psc` source files, decompiled `.pex` outputs, and Behavior/Animations extracts can still create the same shape of trap.

The general principle — loose-overrides-archive becomes a stale trap whenever the archive side changes and the loose side does not — applies to every BGS game and every cross-patch maintenance event. Whenever a previously-stable modded profile breaks after a game update, the stale-loose-extract hypothesis is one of the cheapest tests in the diagnostic ladder, and should be ruled in or out before bisecting the mod overlay.
