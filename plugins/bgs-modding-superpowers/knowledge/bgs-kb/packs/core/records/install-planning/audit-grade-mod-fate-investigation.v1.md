---
id: install-planning.audit-grade-mod-fate-investigation.v1
title: Audit-grade mod fate investigation surfaces 4+ outcomes, not a binary "unusable" verdict
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: A Nexus pulled signal (status=removed/hidden/not_published, 404, available=false) does not justify reporting the mod as "unusable" to the curator. Audit-grade investigation distinguishes at least four outcomes — same-author republish, off-Nexus continuation, dead-listing-functional (the local artifact still works because its essence is simple loose files), and replacement-needed. The reporting discipline is honest, complete information that supports curator decision-making, not a binary verdict that frames replacement as the only option.
  confidence: high
queryKeys:
  - audit-grade investigation
  - mod fate analysis
  - pulled mod investigation
  - mod essence analysis
  - functional usability
  - artifact vs listing
  - audit reporting discipline
  - complete decision information
  - dead-listing-functional
  - mod fate verdicts
severity: high
sources:
  - kind: project-internal-doc
    url: https://github.com/BB-84C/bgs-modding-superpowers/blob/main/docs/modpack-dev-logs/bb84-starfield/dev-log.md
    ref: BB84 2026-06-25 Lane 2 staleness audit correction round — Immersive Data Slates illustration
related:
  - mod-evaluation.investigating-pulled-mods.v1
  - install-planning.mod-update-post-state-discipline.v1
  - mod-evaluation.quality-and-risk-signals.v1
  - install-planning.cc-content-pipeline.v1
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# Audit-grade mod fate investigation surfaces 4+ outcomes, not a binary "unusable" verdict

## The trap of surface classification

When a staleness audit hits an API signal like `status=removed`, `status=hidden`, `available=false`, or `404`, the cheap reflex is to label the mod "Red — unusable, find replacement". This is the wrong reporting shape for two reasons.

First, the Nexus listing is not the artifact. A delisted listing tells the curator something happened to the upstream record: the author hid it, Nexus wastebinned it, the modid was abandoned. None of those facts say anything about whether the **installed files** in the curator's MO2 mod folder still function under the current game runtime. A simple texture pack delisted three years ago is identical at runtime to a published texture pack updated yesterday, if the texture format has not changed.

Second, the curator depends on the audit for decision support, not for a verdict. "X is unusable" closes a door without showing the alternatives. "X is delisted by author; same author has not republished; mod essence is a four-file texture replacement; local artifact still loads under 1.16.244; no security concern" opens an informed choice. The audit's job is to surface the second shape.

## The four-plus outcome distinction

Every pulled signal should resolve into at least one of:

1. **CONTINUITY-REPUBLISHED** — Same author republished under a new modid (per `mod-evaluation.investigating-pulled-mods.v1` continuity tracing). Curator action: lineage reconciliation in `meta.ini modid=` and `installationFile=` to the live listing, then refresh update state.
2. **CONTINUITY-OFF-NEXUS** — Author moved the project off Nexus to GitHub, Patreon, Discord, an alternative mod site, or their own download host. Curator action: re-track the upstream at the new channel; note the dependency on the author's hosting decision.
3. **DEAD-LISTING-FUNCTIONAL** — Nexus listing is gone, but the local installed artifact still functions. Applies when the mod's essence is simple loose files (texture replacement, UI swap, INI tweak, mesh swap) with no dependency on the listing for anything except discovery. Curator action: keep the local copy, mark `meta.ini comments=` that the Nexus source is gone, monitor only for runtime compatibility.
4. **DEAD-LISTING-AT-RISK** — Nexus listing is gone AND the mod has systemic components (esm/esp/esl plugins, Papyrus scripts, runtime hooks, SFSE/SKSE plugin DLLs) that may break with future game patches without an author available to fix. Curator action: keep monitoring, plan replacement, do not panic-remove unless symptoms appear.
5. **REPLACEMENT-NEEDED** — Continuity tracing exhausted, local artifact is degraded or actively broken, no community continuation found. Curator action: search alternative implementations; evaluate per `mod-evaluation.quality-and-risk-signals.v1`.

These are not mutually exclusive at investigation time. A mod can hit DEAD-LISTING-FUNCTIONAL today and shift to DEAD-LISTING-AT-RISK after a future game patch breaks its loose files. The audit captures the current state with notes on transition risk.

## The functional-essence analysis

For the DEAD-LISTING-FUNCTIONAL vs DEAD-LISTING-AT-RISK distinction, the diagnostic is the installed mod folder's actual content. A useful classification:

- **Pure-asset mods** — loose textures (`.dds`), meshes without scripts (`.nif`), sound packs (`.wem`/`.bk2`), UI replacements with no Papyrus. Essence is the file. Listing death does not affect runtime.
- **Plugin-only mods** — `.esm`/`.esp`/`.esl` with records but no Papyrus and no engine hooks. Essence is the form list. Game patches that change form layouts can break them silently. Risk depends on what records they touch (cosmetics, low; quest or cell, high).
- **Scripted mods** — `.esm`/`.esp` plus Papyrus `.pex`. Essence is the script plus runtime. Script extender updates can break compatibility; pulled author leaves no upstream patcher.
- **DLL plugin mods** — SFSE/SKSE/F4SE addon DLLs bound to a specific runtime version. Future runtime changes break them without author support.

The audit-grade report carries this essence classification per pulled mod, alongside the fate verdict. The curator can then decide: "this DEAD-LISTING-FUNCTIONAL texture pack stays for the long haul" versus "this DEAD-LISTING-AT-RISK SFSE DLL goes into a 等待替代品 separator and we monitor".

## The audit-grade reporting discipline

Audit reports should surface the complete picture per pulled or aging mod, not a verdict:

- API-level fate signal (status, available, last update, files endpoint state)
- Continuity investigation result (same-author republish search outcome, off-Nexus channels checked)
- Functional essence analysis (file count breakdown, essence classification)
- Local artifact health (does it still load, any conflict signals, game runtime compat)
- Fate verdict (one of the four-plus outcomes above)
- Recommended curator action with reasoning

Do not collapse this into "Red — needs replacement". The curator has explicitly asked for honest, complete reporting that supports informed decisions. The audit's value is the full picture, not the verdict.

## What "completeness" means in practice

Completeness has a specific shape:

- Surface every distinguishing signal, even when they point in the same direction. Two converging signals strengthen a verdict; surfacing only one hides confidence calibration.
- Surface negative results (continuity searches that found nothing) alongside positive results. Curators need to know what was checked, not only what was found.
- Surface essence honestly. A mod whose folder is one `.dds` file deserves a different report than a mod whose folder is an `.esm` plus 40 `.pex` scripts, even if their Nexus signals are identical.
- Surface uncertainty when it exists. If a `.tif` file in the mod folder cannot be classified confidently, say so; do not invent a verdict.

## Anti-pattern that triggered this rule

In the 2026-06-25 audit dispatch, a fan-out classifier labeled ~50 mods as Red based on simple API signals (`status=removed`, latest-file-age, version-mismatch) and recommended replacement search across the board. Among those entries was Immersive Data Slates — a mod whose essence is a loose texture replacement for in-game data slate readability. The curator pointed out that the mod's essence is harmless to keep regardless of Nexus listing state, and that the binary verdict was masking the actual decision space.

The cost difference matters: investigating and replacing 50 Red mods is a large project; investigating and accepting that 20-30 of them are DEAD-LISTING-FUNCTIONAL with no action needed is hours of work avoided. Surface classification turns audit-grade investigation into make-work, and erodes curator trust in future audit outputs.

## See also

- `mod-evaluation.investigating-pulled-mods.v1` — continuity tracing technique used inside this rule's outcomes 1 and 2.
- `mod-evaluation.quality-and-risk-signals.v1` — when REPLACEMENT-NEEDED applies, replacement candidate evaluation framework.
- `install-planning.mod-update-post-state-discipline.v1` — intent-aware mutation discipline that this audit ultimately feeds into.
- `archive-precedence.stale-ck-extract-loose-files.v1` — analogous principle in another shape: a stale loose file looks valid and silently breaks; a delisted mod looks broken and silently works. Both call for evidence-driven verdicts, not surface classification.
