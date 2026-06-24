---
id: install-planning.nexus-direct-api-update-check.v1
title: Direct Nexus API for update-state refresh (Option B) — bypass MO2 GUI
kind: rule
domains: [install-planning, tooling.loot]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "MO2's `Tools → Check All for Updates` is GUI-only — mobase Python API does NOT expose the trigger and 3 of the 4 target meta.ini fields (`nexusFileStatus`, `lastNexusQuery`, `lastNexusUpdate`) live on the concrete `ModInfoRegular` class not the abstract `IModInterface`. The agent-friendly alternative (Option B) is direct Nexus API: call `GET /v1/games/{game_domain}/mods/{id}.json` for fresh metadata then write back to `meta.ini` via `mo2_edit_meta` or direct PowerShell INI edit. No Premium required for read endpoints. Rate budget 20k/day."
  confidence: high
queryKeys: [Nexus API, update check, lastNexusQuery, newestVersion, nexusFileStatus, Option B, refresh meta.ini, mobase gap]
severity: high
sources:
  - kind: official
    url: "https://help.nexusmods.com/article/105-api-daily-or-hourly-limits"
    ref: "Nexus API rate limits (20k/day, 500/h throttled)"
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/ModOrganizer2/modorganizer/master/src/nexusinterface.cpp"
    ref: "MO2 NexusInterface — APIKEY header path, no Premium gating on TYPE_CHECKUPDATES"
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/Nexus-Mods/node-nexus-api/master/src/Nexus.ts"
    ref: "node-nexus-api SDK — getModInfo + getRecentlyUpdatedMods endpoint shapes"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Direct Nexus API for update-state refresh (Option B) — bypass MO2 GUI

MO2's built-in `Tools → Check All for Updates` action is GUI-only. The public mobase Python surface does not expose a trigger for that action, and the relevant update-state fields mostly live on MO2's concrete `ModInfoRegular` implementation rather than the abstract `IModInterface`. Agents should prefer Option B: use the Nexus API directly for fresh mod metadata, then write the relevant `meta.ini` fields in a controlled, auditable update.

The mobase gap is specific: `setNewestVersion` and `refresh` exist, but the Python API does not provide equivalent setters for `nexusFileStatus`, `lastNexusUpdate`, and `lastNexusQuery`, nor does it expose the GUI's all-mod update scan as an agent-native call. Patching the broker to emulate that GUI path has high blast radius for low marginal value. Direct Nexus reads are simpler, testable, and do not require Premium for the metadata endpoints; they must still respect Nexus rate limits.

Per-mod refresh shape:

```powershell
$mod = Invoke-RestMethod -Uri "https://api.nexusmods.com/v1/games/starfield/mods/$modid.json" -Headers @{
  "APIKEY" = $apiKey
  "Application-Name" = "bgs-modding-superpowers"
  "Application-Version" = "1.0"
}

# Update 4 meta.ini fields:
$content = $content -replace '(?m)^newestVersion=.*$', "newestVersion=$($mod.version)"
$content = $content -replace '(?m)^nexusFileStatus=.*$', "nexusFileStatus=$statusInt"   # 1=published,6=removed,9=hidden
$content = $content -replace '(?m)^lastNexusQuery=.*$', "lastNexusQuery=$nowIso"
$content = $content -replace '(?m)^lastNexusUpdate=.*$', "lastNexusUpdate=$updatedIso"
```

Map Nexus status conservatively: `published` to `1`, `hidden` to `9`, `removed` to `6`, `wastebinned` to `6`, `under_moderation` to `9`, and unknown/default values to `1` unless the API response proves otherwise. For bulk scans, call `/mods/updated.json?period=1m` first to identify mods updated in the last month and avoid per-mod calls for static entries. After writing `meta.ini`, remember that MO2's GUI may not show the new values until `organizer.refresh()` or an app restart reloads `ModInfoRegular` state.

Concrete 2026-06-24 BB84 audit result: direct API refresh over 172 installed Starfield mods found 162 with real updates, while the stale MO2 cache only indicated about 30. That is the value of treating GUI cache as stale until refreshed. The tradeoff is that credential reading and `meta.ini` writes must follow explicit permission and masking rules.
