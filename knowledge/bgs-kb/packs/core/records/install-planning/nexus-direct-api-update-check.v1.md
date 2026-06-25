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

When refreshing per-mod meta.ini in the same pass as writing per-mod
summary text (the typical "audit + describe" combined workflow), write the
short summary to `comments=` (MO2 GUI mod-list column) NOT `notes=` (mod
properties Notes tab — hidden until clicked). See KB record
`engine.xse-update-workflow.v1` cascade section + `mo2-mcp-internals`
memory rule 18 for the field distinction.

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

## Premium download workflow (when API key + premium enables auto-download)

When the API key belongs to a Premium account, `POST /v1/games/{game}/mods/{modid}/files/{file_id}/download_link.json` returns an array of CDN mirror objects, NOT a single URL. Empirically observed mirror set (BB84 2026-06-24 round):

| short_name | URL host | Premium-gated? |
|---|---|---|
| Chicago | chicago-premium.nexus-cdn.com | Yes |
| Amsterdam | amsterdam-premium.nexus-cdn.com | Yes |
| Prague | prague-premium.nexus-cdn.com | Yes |
| Los Angeles | la-premium.nexus-cdn.com | Yes |
| Miami | miami-premium.nexus-cdn.com | Yes |
| Dallas | dallas-premium.nexus-cdn.com | Yes |
| Nexus CDN | cf-files.nexusmods.com | NO — also available to free accounts via browser flow |

All URLs are time-limited signed (Cloudflare query-string auth). The first mirror (`[0]`) is usually fine; for very large files (>500MB) picking a geographically closer mirror reduces transfer time.

For FREE accounts, the same `download_link.json` POST returns `401 Unauthorized` or empty array — the browser-equivalent path requires the user to click "Manual Download" on the mod page, which triggers a JS-side captcha + waiting timer + then returns a single `cf-files.nexusmods.com` URL via the Nexus.com session. The agent cannot drive this flow autonomously without browser automation.

Agent-friendly recommendation: if user has Premium, use `download_link.json`. If free user, surface the manual download URL + ask user to provide the downloaded archive path.

## Backup-before-update convention

For any agent-driven mod update workflow, back up the existing MO2 mod folder BEFORE replacing files. Convention proven across SFSE binary updates, Address Library updates, batch SFSE plugin updates, and CharGenMenu modid-fix updates this round:

```
<MO2Root>/.backups/<modName>-<oldVer>_pre-<newVer>-update_<timestamp>/
```

- `<modName>` matches the MO2 mod folder name exactly (preserving any version tags in the folder name like `- AddLib 22` or `- Game version 1.16.244`).
- `<oldVer>` is the meta.ini `version=` value BEFORE the update.
- `<newVer>` is the target version.
- `<timestamp>` is `yyyy-MM-dd_HHmm`.

The backup directory is a deliberate sibling of the mods/ tree (so MO2 doesn't see it as a mod). Rollback = `Copy-Item <backup>\* <modDir>\` + revert meta.ini fields.
