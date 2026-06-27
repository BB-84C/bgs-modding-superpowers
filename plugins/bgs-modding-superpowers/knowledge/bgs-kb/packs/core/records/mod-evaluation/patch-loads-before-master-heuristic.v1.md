---
id: mod-evaluation.patch-loads-before-master-heuristic.v1
title: When a patch loads before its declared master without engine error, the master declaration is probably absent and the patch is suspect
kind: rule
domains: [load-order, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: A plugin that names itself "<X>-patch" or "Patch-<X>" but loads before the plugin <X> without producing a missing-master error is broadcasting two facts at once. First, the engine did not enforce master-ordering, which means the patch's TES4 header does not actually declare <X> as a master (or the master declaration is so loose the engine treats it as soft). Second, that absence is unusual for a "real" patch — patches that actually edit records owned by their parent must declare the parent as a master, because the FormID prefix bytes refer to the parent's mod index. The combined signal is that the patch may be experimental, vestigial, empty, or a stale relic of an earlier authoring attempt. Move it to a winning position so worst-case it does nothing, then verify content in xEdit.
  confidence: high
queryKeys:
  - patch loads before master
  - patch declared master missing
  - patch no master declaration
  - load order anomaly diagnosis
  - patch is empty or vestigial
  - half-finished patch detection
  - rvspace-patch diagnostic
  - inferring mod reality from load order behavior
  - patch master declaration check
  - lazy patch authoring detection
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-28 Lane 3 pre-flight rvspace-patch.esm diagnostic intuition
related:
  - load-order.official-cc-as-vanilla-baseline.v1
  - plugin-format.tes4-hedr-master-list.v1
  - debugging.asymmetric-evidence-self-falsify.v1
  - install-planning.mod-update-post-state-discipline.v1
lastReviewed: "2026-06-28"
schemaVersion: 1
---

# When a patch loads before its declared master without engine error, the master declaration is probably absent and the patch is suspect

## Perspective: OBJECTIVE

This rule converts a load-order observation into structural inference about the plugin file itself, then into an evaluation heuristic about whether the mod is worth keeping. The chain is one logical step but compresses a real engine fact: the Creation Engine enforces master-ordering at plugin load time. If that enforcement is silent for a self-named "patch", the master list is wrong or absent.

## The observation

A plugin file in the load order is named in a way that strongly suggests it is a patch for another plugin. Common shapes:

- `<X>-patch.esm`, `<X>-Patch.esm`, `Patch-<X>.esm`
- `<X>-<Y>-patch.esm` for cross-mod compatibility patches
- `<X>_FIX.esm`, `<X>_Compatibility.esm`

The "patch" loads earlier in the load order than the plugin it claims to patch. The game still starts. The plugin still loads. There is no `Missing Masters` warning in MO2 GUI, no engine error, no plugin disable.

That combination is the diagnostic signal.

## What the engine actually enforces

Real master declarations in a plugin's TES4 header (the MAST + DATA subrecord pairs) carry two consequences at runtime:

1. The engine forces masters to load BEFORE the plugin that declares them. If MO2 or `plugins.txt` tries to invert that, MO2 surfaces a Missing Masters dialog and the offending plugin is treated as unloaded.
2. The plugin's records can reference the master's FormIDs by using the master's load-order index in the high byte. Without a master declaration, those references are invalid and the engine cannot resolve them.

If a "patch" silently loads ahead of its target without error, neither consequence fired. The master declaration that would have produced consequence #1 is not in the TES4 header. By extension, the patch cannot legitimately reference the parent's FormIDs either.

## What that implies about the patch

If the patch does not declare the parent as a master, then one of four things is true:

1. The patch was never finished. The author started a compatibility shim, never added MAST entries, and the file sat in the load order doing nothing. Common for personal/experimental work that was paused.
2. The patch is an empty stub. A plugin file with valid TES4 framing but no edit records will load fine without master declarations because it has no FormIDs to resolve. Authors sometimes ship these as placeholders.
3. The patch edits a different surface than the name suggests. It may modify global records (game settings, MGEF, etc.) that don't require the named parent as a master.
4. The patch carries content but is genuinely buggy. The author shipped without realizing the engine wasn't enforcing ordering against the intended parent. The "patch" may be partially effective on global records while completely silent on parent-owned records.

In all four cases, the patch's semantic identity ("this fixes/extends <X>") is at minimum partially wrong. Trusting the patch's name as ground truth is the failure mode.

## The diagnostic workflow

1. **Don't disable the patch immediately.** It may be doing something on global records.
2. **Move the patch to a winning position** (load after its declared parent, ideally `wins_over <parent>` in mo2-mcp vocabulary). If the patch is empty or has no overlap with the parent, the move costs zero. If the patch has real content that requires winning, the move fixes the pre-existing bug. Worst case: no change.
3. **Audit in xEdit** as part of the next conflict pass. Look for:
   - TES4 header MAST entries. If `<parent>.esm` is missing from the master list, your heuristic is confirmed.
   - Edit record count. An empty patch (no records beyond TES4) is the strongest case for archival.
   - Records that touch global forms (GMST, MGEF, FACT, KYWD) — these can exist without a parent master and explain why the patch was loadable.
   - Records with FormIDs in the `<parent>` index range. If present, the patch was bugged: it carries parent-owned records but did not declare the master, so the references are broken in-engine.
4. **Decide based on xEdit audit**. Empty stub → archive. Effective on global records only → keep but rename to reflect what it actually does. Bugged with broken parent references → either fix the master list or archive depending on whether anyone needs it.

## When NOT to apply this rule

This heuristic is for **author-published patches that name a specific parent and load ahead of it without error**. It does not apply to:

- Plugins that are not named as patches (a `texture_pack.esm` loading early is just early).
- Patches where the engine DID produce a Missing Masters warning — the warning is the engine catching the problem and the master declaration is present.
- Cross-game-version patches that are intentionally master-light (some bug-fix mods modify GMST only and have no parent master by design).
- ESL-flagged "patches" where the FormID scheme works differently and the rule's reasoning needs adjustment.

The rule is also weaker for `.esp` patches than `.esm` patches because some authors use `.esp` files as standalone overrides where the patch identity is more rhetorical than structural.

## The mindset to carry

A plugin's filename is documentation. The TES4 header is fact. When the documentation and the fact disagree at load time, trust the fact and treat the documentation as suspect. A "patch" that the engine treats as a free-floating plugin is not a patch in any meaningful sense — it is a plugin with patch-shaped marketing.

## Concrete illustration

In a 2026-06-27 Lane 3 pre-flight audit of BB84's Starfield modpack, the curator flagged `rvspace-patch.esm` at load_order 55 ahead of `rvspace.esm` at load_order 173 — a 118-position inversion. The fact that the game ran for months in this state with no Missing Masters warning, combined with the curator's vague recollection of having authored the patch experimentally six months earlier, was the diagnostic signal.

The curator's hypothesis: "this plugin loaded before its supposed master without breaking, so it probably never declared rvspace as a master in the first place, which means whatever I put in it is either nothing or working on global records." The reframe carried through: move the patch to win over rvspace anyway (cost zero if empty, fixes the bug if real), and flag for xEdit audit to confirm content versus emptiness.

The cost asymmetry made the move cheap: if the patch was empty stub, the new position changes nothing. If the patch had real content, the new position fixes a pre-existing functional bug. The xEdit audit converts uncertainty into ground truth on a single pass.

## See also

- `load-order.official-cc-as-vanilla-baseline.v1` — a related curation heuristic: official Bethesda Creations packs should be treated as vanilla baseline regardless of whether they declare hard masters.
- `plugin-format.tes4-hedr-master-list.v1` — the underlying engine fact this heuristic exploits.
- `debugging.asymmetric-evidence-self-falsify.v1` — meta-heuristic about not trusting first impressions in diagnostics; this rule is the inverse, trusting a *structural* asymmetry that survives the self-falsification check.
- `install-planning.mod-update-post-state-discipline.v1` — covers intent-vs-effect for live modlists; this rule covers identity-vs-content for plugin files.
