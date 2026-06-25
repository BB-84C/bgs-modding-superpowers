---
id: engine.mo2-process-locking-semantics.v1
title: MO2 process locks plugins/modlist/INI in memory but NOT mods/ — installs don't need MO2 closed
kind: gotcha
domains: [engine, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: MO2 holds the active profile's `plugins.txt`, `modlist.txt`, and per-profile `*.ini` files in memory while it runs and rewrites them on exit, so direct edits to those files are clobbered when MO2 closes. However MO2 does NOT lock the `mods/` tree — new mod folders dropped under `mods/<NewMod>/` are picked up by MO2's filesystem watcher on the next refresh, no restart required. Closing MO2 only for mod installs is unnecessary overhead and forces avoidable session interruptions.
  confidence: high
queryKeys:
  - MO2 close required
  - install mod without closing MO2
  - modlist.txt clobbered
  - plugins.txt rewritten on close
  - MO2 filesystem watcher
  - MO2 mod folder auto-detect
  - MO2 process locking
  - when to close MO2
severity: medium
sources:
  - kind: tooling-docs
    ref: ModOrganizer2 source — settings.cpp profile-file persistence pattern
    url: https://github.com/ModOrganizer2/modorganizer
  - kind: project-internal-doc
    ref: BB84 2026-06-25 audit correction — agent unnecessarily closed MO2 before mod installs
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# MO2 process locks plugins/modlist/INI in memory but NOT mods/ — installs don't need MO2 closed

## Perspective: OBJECTIVE

MO2's process-state contract is asymmetric in a way that confuses agents who treat it as a uniform "is locked or not" question.

## What MO2 holds in memory while running

These files are read at MO2 startup, kept in memory while running, and rewritten on exit. Direct filesystem edits made while MO2 is running are silently overwritten on close:

- `<MO2Root>/profiles/<profile>/plugins.txt` — plugin activation + order
- `<MO2Root>/profiles/<profile>/modlist.txt` — mod folder enable + order + separator structure
- `<MO2Root>/profiles/<profile>/*.ini` — per-profile game INI overrides (Starfield, Fallout4, etc.)
- `<MO2Root>/ModOrganizer.ini` — instance settings

If an agent edits these files directly while MO2 is running, the edits survive only until the next MO2 close. The mo2-mcp `mo2_*` tools route through MO2's broker pipe when alive (live IPC, no clobber risk), and fall back to atomic file rewrites when MO2 is closed. Both modes are safe; the broker is preferred when available.

## What MO2 does NOT lock

These surfaces are watched, not locked. Agents can write to them while MO2 is running and MO2 will pick up the changes on its next refresh:

- `<MO2Root>/mods/<NewMod>/` — new mod folder creation. MO2's filesystem watcher detects it and the mod appears in the GUI on next refresh (or immediately if the user manually triggers refresh).
- `<MO2Root>/mods/<ExistingMod>/<file>` — modifications to existing mod folder contents. MO2 re-stats the tree as needed.
- `<MO2Root>/downloads/` — new download arrivals.
- `<MO2Root>/overwrite/` — runtime spill from launched processes.

For an agent installing a new mod (download to `downloads/`, extract to `mods/<modname>/`, write `meta.ini`), MO2 does not need to be closed. The mod appears on the next refresh. The orchestrator may need to call `mo2_toggle_mod` afterwards to enable it, which goes through the broker if MO2 is alive — also safe.

## When closing MO2 is genuinely required

- Editing `plugins.txt` / `modlist.txt` / `*.ini` directly via filesystem (not via mo2-mcp). The mo2-mcp tools handle this for you when MO2 is closed.
- Switching profiles via `ModOrganizer.ini` `selected_profile=` edit. Requires MO2 closed.
- Cloning, renaming, or deleting a profile (MO2 holds open handles inside the profile dir).
- Replacing MO2 itself or the game plugin DLL (`plugins/game_*.dll`).

For most modpack-curation actions — install, enable/disable, reorder, write notes, edit metadata — there is no need to close MO2 if the action goes through mo2-mcp (which routes through the broker when alive).

## Why this matters

Closing MO2 to install a mod has three avoidable costs:

1. **Session disruption** — the curator's GUI state, expanded separator views, mod selection, and Notes-tab focus are all lost.
2. **Re-scan cost** — MO2's startup re-stats `mods/`, re-parses `plugins.txt`, and re-applies per-profile INI overrides. On a 400-mod modpack this is several seconds plus disk churn.
3. **Workflow interruption** — agents close MO2, the curator has to re-open it after each install batch, then close it again for the next batch.

The cheap discipline is to use mo2-mcp through the live broker when MO2 is running, and to use direct file edits only when MO2 is closed. The expensive anti-pattern is "close MO2 before every install just to be safe".

## What changes after the install

- If the install added new `.esm`/`.esp`/`.esl` plugins, MO2 will surface them as unmanaged on next refresh — `mo2_toggle_plugin` activates them.
- If the install was a patch with no new plugins (just loose files), no plugin-side action is needed.
- For pre-installed plugins that just changed enable state, MO2 reloads its mod-folder state automatically.

## See also

- `install-planning.audit-grade-mod-fate-investigation.v1` — for audit workflows that don't need to close MO2 either.
- `archive-precedence.stale-ck-extract-loose-files.v1` — for the case where direct game-install mutations are required and MO2 closure is not the relevant boundary.
