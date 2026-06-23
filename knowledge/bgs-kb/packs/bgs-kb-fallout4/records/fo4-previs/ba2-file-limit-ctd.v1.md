---
id: fo4-previs.ba2-file-limit-ctd.v1
title: Fallout 4 can crash at startup when the load order exceeds the BA2 archive ceiling
domains: [archive-precedence, debugging, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
canonical:
  answer: If Fallout 4 crashes at startup while plugin count is under the ESP/ESM ceiling, a high BA2 count plus Buffout4 LooseFileAsyncStream evidence points to the BA2 archive limit rather than ordinary plugin load order.
  confidence: high
queryKeys: [BA2 limit, BA2 ceiling, startup CTD, LooseFileAsyncStream, Buffout4 BA2, Archive2, BAE, repack BA2]
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 FO4 BA2-limit fix article extraction
related: [fo4-tooling.ba2-asset-tools-need-runtime-awareness.v1, fo4-buffout.crash-log-first-pass-triage.v1]
lastReviewed: "2026-06-23"
schemaVersion: 1
---

# Fallout 4 can crash at startup when the load order exceeds the BA2 archive ceiling

Fallout 4 can hit a startup crash caused by too many BA2 archives even when the ESP+ESM count is still below 255. Do not diagnose this as a normal plugin-count failure unless the archive count has been ruled out.

The practical diagnostic pattern is: plugin count is below the usual ceiling, disabling a BA2-providing mod lets the game start, and a Buffout4 crash log includes `LooseFileAsyncStream*` evidence. That combination points at archive streaming pressure rather than a single bad record override.

A common workaround is to reduce the number of BA2 files. Start with the smallest archives visible in MO2's Data tab. Extract small BA2s with BAE, then either leave them loose in one controlled mod or repack them with Archive2 into fewer archives.

When repacking, keep Fallout 4's naming and asset-type conventions: non-texture assets go into a `<NAME> - Main.ba2`, textures go into `<NAME> - Textures.ba2`, and a blank `<NAME>.esp` can be used to load the archive pair. Load the consolidation mod late enough that its assets win where intended, and keep the original mods disabled so the old BA2 files no longer count.
