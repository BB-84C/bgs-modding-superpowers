---
id: papyrus.script-impact-scope-inference.v1
title: Inferring Papyrus mod impact scope from file-level signals before xEdit audit
kind: rule
domains: [papyrus, install-planning, file-conflicts]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: |
    Papyrus mod impact rarely resolves through filename conflicts; it resolves through internal script logic plus formID-data interaction. But before opening xEdit or decompiling .pex, file-level signals — script naming namespace, source .psc shape (Native Hidden stubs vs script bodies), packaged-vs-loose .pex distribution, accompanying ESM size, and SFSE DLL presence — let an agent infer narrow vs mainstream scope. The key heuristics are: Native Hidden stubs of vanilla-named scripts are SFSE handle declarations (narrow); own-namespace .pex (mod prefix as subfolder under scripts/) is content-additive (narrow); custom quest-fragment naming qf_* / tif_* indicates new-quest authoring not vanilla replacement (narrow); loose .pex at scripts/<vanilla_script_name>.pex shadowing a real vanilla compiled script is the structural red flag (mainstream-invasive).
  confidence: high
queryKeys:
  - papyrus scope inference
  - script namespace heuristic
  - native hidden stub
  - vanilla script override detection
  - own-prefix vs vanilla-prefix pex
  - quest fragment naming
  - papyrus framework scope
  - SFSE papyrus extender
  - pre-xedit script audit
  - papyrus file-level signals
  - BA2-packaged script enumeration
  - companion ESM size signal
severity: medium
sources:
  - kind: project-internal-doc
    url: https://github.com/BB-84C/bgs-modding-superpowers/blob/main/docs/modpack-dev-logs/bb84-starfield/dev-log.md
    ref: BB84 2026-06-27 Lane 3 pre-flight v3 — Cassiopeia Papyrus Extender Native Hidden stub verification; Dark Universe - Crossfire qf_*.pex custom-quest-fragment confirmation; Ship Vendor Framework 4 vanilla script overrides; VASCO-9000 / No Sound In Space zero-script confirmation
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-preflight/lane-B-report.md — Cassiopeia Native Hidden stub direct .psc inspection
related:
  - papyrus.vanilla-script-modification-red-flag.v1
  - papyrus.base-form-vs-reference-script-scope.v1
  - starfield-save-hygiene.script-baking.v1
  - mod-evaluation.conflict-count-vs-behavior-impact.v1
  - skyrim-scripts.loose-pex-over-bsa.v1
  - archive-precedence.loose-over-archive.v1
  - fo4-papyrus.f4se-papyrus-extensions-runtime-bound.v1
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# Inferring Papyrus mod impact scope from file-level signals before xEdit audit

## Perspective: OBJECTIVE

## What Papyrus conflicts are NOT

Papyrus conflicts rarely resolve through `.pex` filename collisions. Two mods seldom ship identically-named `.pex` files unless one is intentionally patching the other. The dangerous Papyrus conflicts are behavior-level: multiple mods modifying the same vanilla quest's runtime logic, two mods registering events on the same vanilla form, a script extender plugin and a Papyrus-side mod fighting over the same global state, or a vanilla `.pex` replacement breaking every mod that depends on the original. None of these show up as `.pex` filename collisions in a file-level scan.

That makes file-level Papyrus signals look misleadingly safe. A mod with 1500 `.pex` files inside its BA2 may have zero filename collisions yet still rewrite mainstream vanilla quest behavior — or it may add a wholly self-contained creature companion subsystem with zero vanilla interaction. The file scan cannot tell the difference.

## Pre-xEdit inference heuristics

Before opening xEdit (which is the authoritative tool), several file-level signals let an agent infer narrow vs mainstream scope. None of these are conclusive on their own; they triangulate.

### Heuristic 1 — Script namespace

- **Own-namespace `.pex`** (`scripts/<modprefix>/X.pex`, `scripts/xenomaster/foo.pex`, `scripts/du_overtime/bar.pex`): content-additive, almost always narrow scope. The mod's scripts live in their own folder under `scripts/` and don't shadow vanilla scripts.
- **Bare `scripts/X.pex`** (no subfolder): ambiguous. Could be a vanilla replacement (red flag) OR a custom script the author placed at the root for their own reasons. Cross-check against known vanilla script names.
- **Vanilla-name `scripts/Actor.pex` / `scripts/ObjectReference.pex` / `scripts/Quest.pex` / etc.**: structural red flag per `papyrus.vanilla-script-modification-red-flag.v1`. Verify it is not a `Native Hidden` stub (see heuristic 2) before concluding.

### Heuristic 2 — `.psc` source body shape

If the mod ships `.psc` sources (many do, both in `scripts/source/user/` and inside the BA2), open the suspicious file. The two patterns matter:

- **`Native Hidden` stub** (one line, ends with `Native Hidden`):
  ```
  Scriptname ArmorAddon extends Form Native Hidden
  ```
  This is an SFSE / F4SE / SKSE handle declaration. The C++ DLL plugin attaches native functions to this Papyrus type at runtime. It does NOT replace vanilla `ArmorAddon` behavior. Cassiopeia Papyrus Extender, PapyrusExtender, JContainers, and similar mods all use this pattern. Narrow infrastructure scope; the file count is misleading.
- **Full script body** (`Event OnInit() / Function X() / State Y / ...`):
  This is real Papyrus code. If the script name matches a vanilla script, this is the structural red flag. If the script name is in the mod's own namespace, the body is custom content (narrow).

### Heuristic 3 — Custom quest-fragment naming

Vanilla quest-fragment scripts follow a fixed naming convention generated by the Creation Kit:
- `qf_<QuestName>_<FormID>` for quest fragments
- `tif_<QuestName>_<FormID>` for topic-info fragments
- `frag_<QuestName>_<FormID>` for older fragment styles
- `term_<TerminalName>_<FormID>` for terminal fragments

These names are unique per quest. When a mod ships `scripts/qf_spawnships_addsingleinstallation.psc` or `scripts/xenomaster/fragments/tif_aag231xenomastermainques_01003d82.pex`, the author is shipping NEW quest content using vanilla CK fragment naming. The `qf_spawnships_addsingleinstallation` is a Dark Universe - Crossfire custom quest fragment; it does NOT replace a vanilla `qf_*` script because vanilla scripts have different FormID suffixes.

When you see `qf_*` / `tif_*` / `frag_*` / `term_*` at `scripts/X.pex` with a mod-specific name, that's content addition, not vanilla replacement.

### Heuristic 4 — Accompanying ESM size + record types

A mod's `.esm` size correlates loosely with the breadth of records it ships:
- **<1 MB ESM with scripts**: usually narrow — adds a handful of new items / forms / aliases, plus their scripts.
- **1-5 MB ESM**: medium — could be a quest mod, a vendor framework, a content addition with leveled-list injection.
- **>5 MB ESM**: usually mainstream-touching — interior cell overrides (lighting overhauls), worldspace edits, large content additions, or framework with many vanilla form references.
- **>20 MB ESM**: definitely mainstream — large content packs, worldspace overhauls, total faction reworks.

When the ESM is large but file wins are small (Enhanced Lights and FX: 48 wins, 7.5 MB ESM), the ESM is the real conflict carrier. xEdit will surface this; the file-level rubric must flag it as `LOW-COUNT-HIGH-IMPACT` per `mod-evaluation.conflict-count-vs-behavior-impact.v1`.

### Heuristic 5 — SFSE DLL presence

A `sfse/plugins/<name>.dll` (or `skse/plugins`, `f4se/plugins`) signals a native-code engine hook. The DLL operates beneath the Papyrus layer and can intercept any engine function. Two implications:

- The mod's behavior surface is potentially much larger than the Papyrus scripts suggest. Souls of Cities 10.0 ships `ModularPeopleSystem.dll` plus per-city `.txt` config files; the DLL replaces crowd NPC generation in mainstream cities at native code level, invisible to Papyrus or plugin-record analysis.
- DLL plugins are runtime-version-bound. They break across SFSE / SKSE / F4SE updates, and pulled-author mods become hard to maintain.

### Heuristic 6 — Packaged-vs-loose .pex distribution

`Get-ChildItem -LiteralPath "<mod>" -Recurse -Filter *.pex` returns only LOOSE `.pex`. A mod that packages all its scripts inside `Mod - Main.ba2` will report `pex_count: 0` to a substrate scan. To enumerate packaged scripts, either:

- Open the BA2 with `bgs-archive list <archive>` and grep for `.pex` entries.
- Use MO2's conflict view (which sees archive contents post-VFS) and read the per-mod `.pex` win count from the conflict report.

When loose `pex_count = 0` but the conflict report shows many `.pex` wins for the mod, the scripts are inside the BA2. That is not a red flag in itself (it's the normal author pattern); it just means file-level loose inspection is insufficient and xEdit / BA2 enumeration is the next step.

## When to escalate to xEdit / BA2 enumeration

The file-level rubric produces a Lane 3 priority queue. Escalate to xEdit FormID audit OR BA2 `.pex` enumeration when:

1. The mod is classified `mainstream` scope AND vanilla-script-modification is `unclear` (the description claims no vanilla override, but the framework hooks Story Manager / quest aliases / faction relationships).
2. The mod has high save-bake risk (active quest + aliases + persistent state + `OnPlayerLoadGame` handler) and the curator needs to verify the architecture before commitment.
3. Loose `pex_count = 0` but the conflict report shows >50 packaged `.pex` wins — BA2 enumeration reveals the script names, which then route back to heuristics 1-3.
4. The mod ships a SFSE DLL plus Papyrus scripts — the DLL's exact hook surface needs runtime documentation or source review.

## Cross-reference

- `papyrus.vanilla-script-modification-red-flag.v1` — the structural red flag when heuristic 1 + heuristic 2 confirm vanilla script body replacement.
- `papyrus.base-form-vs-reference-script-scope.v1` — script attachment site matters for runtime scope.
- `starfield-save-hygiene.script-baking.v1` — save-bake risk classification (the 3rd signal in the v1 conflict-count rubric).
- `mod-evaluation.conflict-count-vs-behavior-impact.v1` — bidirectional rubric this record supplies the Papyrus-specific heuristics for.
- `skyrim-scripts.loose-pex-over-bsa.v1` — analogous Skyrim-specific note on loose `.pex` precedence.
- `archive-precedence.loose-over-archive.v1` — runtime precedence rule when a loose `.pex` shadows an archived one.
- `fo4-papyrus.f4se-papyrus-extensions-runtime-bound.v1` — F4SE extension binding analogue.
