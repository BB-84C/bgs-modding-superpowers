---
name: maintaining-modding-environments
description: "Use after first-run for ongoing modpack maintenance: update/install KB packs, author or register custom/mod KB packs, maintain localization glossary KBs for translator use, prune KB cache, health-check the environment, version-pin KB/tooling, or handle recurring BGS modding environment care."
---

# Maintaining Modding Environments

## When to use

- The environment is already set up and the user asks to maintain, refresh, update, or health-check it.
- The user says "register custom pack", "install my KB pack", "set `BGS_KB_USER_PACKS`", or asks how to author a local KB pack.
- The user asks how to maintain a mod knowledge base, a translator glossary KB, or a third-party localization KB for Skyrim/Fallout/Starfield.
- The user asks to install, upgrade, repair, or verify the standalone
  `xtl`/`bgs-translator` CLI after first-run.
- The user asks to check or apply knowledge-base updates after first-run.
- The user asks to prune the KB cache or clean old pack versions.
- The user asks whether to pin a KB pack version, follow latest, or handle a `minPluginVersion` warning.

## What this skill replaces

Use `setting-up-bgs-modding-environment` for first-run: MO2 detection, control-plane install, visible MO2 launch, first xEdit acquisition, first KB pack acquisition, and first semantic smoke.

This skill owns ongoing care after that first-run boundary: KB updates, cache hygiene, custom-pack authoring and registration, translator CLI maintenance, recurring environment health checks, and version-pinning advice.

## Translator CLI maintenance

`xtl` is the standalone AI translation CLI/Web GUI launcher. It is published on
PyPI as `bgs-translator`; the portable plugin may include translator-facing
skills, but a fresh user machine still needs the Python package installed before
high-speed agents can call `xtl`.

Start every maintenance pass with an explicit readback:

```powershell
# Check whether xtl is installed and can report its version/capabilities.
xtl version

# Inspect top-level commands before choosing a workflow.
xtl --help
```

If `xtl` is missing or too old, prefer an isolated user-level CLI install:

```powershell
# Install the current release-candidate build as an isolated command-line tool.
pipx install bgs-translator==0.9.0rc1

# Upgrade an existing pipx-managed xtl install when a newer stable build exists.
pipx upgrade bgs-translator
```

If `pipx` is unavailable, or the user explicitly wants `xtl` inside a project
virtual environment, use Python's package installer from that environment:

```powershell
# Install or upgrade xtl inside the selected Python environment.
py -3.12 -m pip install --upgrade bgs-translator==0.9.0rc1
```

For a future stable release, use the unpinned package name for normal installs:
`pipx install bgs-translator`, `pipx upgrade bgs-translator`, or
`py -3.12 -m pip install --upgrade bgs-translator`. Do **not** use broad
`--pre` during routine maintenance; it can allow prerelease dependency versions
that were not part of the tested translator build. Pin an exact prerelease only
when the user intentionally wants that version.

After any install or upgrade, inspect subcommand help instead of assuming
specific option values:

```powershell
# Verify provider-profile setup options, including all supported SDK kinds.
xtl profile add --help

# Verify web GUI launch options and ports.
xtl gui --help

# Verify batch controls before telling an agent to submit or resume work.
xtl batch --help
```

If a GUI or background translator service gets into an inconsistent state,
restart it with the repo's reusable helper instead of inventing process-kill
steps:

```powershell
# Restart the translator GUI/service stack using the project helper.
pwsh tools\bgs-translator\scripts\restart-web-gui.ps1 -Port 7847
```

If that helper is absent in an older checkout, fall back to the current
`using-bgs-translator` instructions for launching `xtl gui`, then file a note in
the environment maintenance log that the helper should be added or backported.

## Check + apply KB updates

1. Start with `bgs_kb_status({})` to see loaded packs, versions, cache root, user roots, and warnings.
2. If `bgs_kb_check_updates` exists, call it for the installed pack IDs. Surface available updates, `breakingChange`, and release URLs before taking action.
3. If `bgs_kb_check_updates` is not present yet (pre-KB-6), check GitHub Releases for `bgs-modding-superpowers` KB pack artifacts and `manifest-index.json`. Do not invent release names.
4. Before installing or replacing a pack, get user consent for the download / cache mutation.
5. If `bgs_kb_install_pack` exists, use it with an exact `{ packId, version }`. Prefer `dryRun: true` before live install when the tool supports it.
6. If the install tool is not present yet, download the Release asset manually only after consent, verify the published sha256, extract into the cache layout below, then restart or reconnect the MCP so discovery runs again.
7. After any update, run the health checks below.

## Cache hygiene

Cache root (all platforms — unified with `xtl` / `bgs-translator`):

```text
~/.bgs-modding-superpowers/kb/packs/<packId>/<version>/
```

The legacy Windows-only cache at `%LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/`
is **no longer used**. If `bgs_kb_status` surfaces packs that are not visible to
`xtl batch plan`, suspect a legacy cache and either:

- move the directory tree from `%LOCALAPPDATA%/bgs-modding-superpowers/kb/` to
  `~/.bgs-modding-superpowers/kb/`, or
- export the legacy root via `$env:BGS_KB_USER_PACKS` so the MCP keeps reading
  it as an additional read-only root while the user finishes migrating.

Each version directory contains `manifest.json`, `records/`, and `kb.sqlite`. Current policy: retain the current version and the immediately previous version as rollback/fallback. Prune versions older than that only after confirming the pack is not pinned by the user or referenced by a current modpack workflow.

Use the KB MCP CLI for routine pruning:

```powershell
# Preview which cached pack versions would be removed.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js prune-cache --dry-run

# Apply the prune after the user accepts the preview.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js prune-cache
```

The dry run should be surfaced before deletion when the user has not already approved cache mutation. The command keeps the highest version and the immediately previous version per pack, then removes older cached versions.

Do not delete `incoming/` while an install is running. If an install failed earlier and no installer is active, stale `incoming/` contents can be removed after surfacing the path to the user.

## Custom pack authoring + registration

Author records as:

```text
<pack-root>/records/<domain>/<id>.md
```

Record frontmatter uses the same schema as official packs under `knowledge/bgs-kb/schema/record.schema.json`: stable `id`, `title`, `domains`, `appliesTo`, `canonical`, `sources`, `lastReviewed`, and `schemaVersion` are the important fields to check first.

Every pack needs a `bgs-kb-meta.yml` at the pack root. Minimum fields:

```yaml
packId: user-my-pack
displayName: My Modpack Knowledge
version: 2026.06.02
schemaVersion: 1
minPluginVersion: 0.2.0
```

Reserved official pack IDs: `bgs-kb-core`, `bgs-kb-skyrim`, `bgs-kb-fallout4`, `bgs-kb-fallout3-fnv`, `bgs-kb-starfield`. End-user packs must not use the `bgs-kb-*` namespace; recommend a `user-*` prefix.

Build the pack:

```powershell
# Build kb.sqlite and manifest.json from the pack's records/ tree.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js build <pack-root>
```

This produces `kb.sqlite` and `manifest.json` next to `records/`.

Validate and inspect:

```powershell
# Validate every Markdown record against the official KB schema.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js validate <pack-root>

# Inspect pack metadata, counts, games, and domains.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js info <pack-root>
```

Important `BGS_KB_USER_PACKS` semantics: each entry is a directory that contains one or more pack directories, not a pack directory itself. Multiple roots are separated by `;` on Windows.

Worked example:

```text
C:\my-kb-roots\
  my-custom-pack\
    bgs-kb-meta.yml
    manifest.json
    kb.sqlite
    records\
      load-order\
        my-local-rule.v1.md
```

Set:

```powershell
# Point discovery at the directory that contains one or more pack folders.
$env:BGS_KB_USER_PACKS = "C:\my-kb-roots"
```

Do not set it to `C:\my-kb-roots\my-custom-pack`; that points at the pack itself and discovery will look one level too deep.

After registration, restart/reconnect the MCP so pack discovery runs, then call `bgs_kb_status({})` and verify the custom pack appears with the intended `packId`.

## Pack discovery + collision recovery

`bgs_kb_status({})` may report two warning codes when discovery sees the same `packId` at multiple roots:

| Code | Meaning |
|---|---|
| `pack_id_overridden` (MEDIUM, informational) | Multiple sources for the same `packId`; precedence picked a winner automatically and listed the loser(s). All packs still load. |
| `pack_id_collision` (HIGH, fail-closed fallback) | Precedence could not choose a winner — should be rare; all colliding copies are refused. |

**Discovery precedence (apply in order):**
1. Sort candidates with the same `packId` by `builtAt` timestamp DESC — newest manifest wins.
2. Tie-break by root class: `bundled > cache > user`.

**Common cause: `install-pack` over an already-bundled `packId`.** Plugin distributions ship per-game packs (e.g. `bgs-kb-fallout4`) in the bundled tree. If a user runs `bgs_kb_install_pack({ packId: "bgs-kb-fallout4", ... })` to fetch a Release-channel update, the new version lands in the cache root `~/.bgs-modding-superpowers/kb/packs/bgs-kb-fallout4/<version>/`. On the next MCP restart:

- If the cache copy has a newer `builtAt` (the normal update case) → cache wins, bundled loser warning. No action needed.
- If the bundled copy is somehow newer (e.g. you pulled a plugin update that shipped a newer KB) → bundled wins, cache becomes the loser. To make the cache copy authoritative, install a newer Release or remove the stale cache copy.

**Other causes:**

- Two `$BGS_KB_USER_PACKS` parent directories contain pack folders with the same `packId` → warning per loser.
- Manual file copy of a pack between roots without removing the original.

**Preview before restarting MCP:** the bgs-kb-mcp CLI exposes a read-only `dev-status` subcommand that shows the same discovery decision the MCP would make, without requiring a server restart:

```powershell
# Preview every discovered packId, every candidate source, and which one would win.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js dev-status

# Filter to one pack id (useful before install-pack or before editing user packs).
node <plugin>\tools\bgs-kb-mcp\dist\cli.js dev-status --pack bgs-kb-fallout4

# Machine-readable output for scripting.
node <plugin>\tools\bgs-kb-mcp\dist\cli.js dev-status --json
```

**Recovery patterns:**

- **Want the cache copy to win**: ensure its `builtAt` is newer than the bundled copy's (run `bgs_kb_install_pack` for a fresh Release version), restart MCP, verify.
- **Want the bundled copy to win**: remove or rename the cache pack directory, restart MCP.
- **Two user roots collide**: drop one parent from `$BGS_KB_USER_PACKS`, or rename the colliding pack folder to a unique `packId` (after also updating its `bgs-kb-meta.yml`), restart MCP.
- **Pre-flight before authoring or installing**: always run `dev-status --pack <packId>` first — it surfaces collisions before the next MCP restart turns them into status warnings.

Do not delete cache copies aggressively as a first-line fix; the precedence rule selects automatically, so warnings are usually informational, not blocking.

## Localization and translator KBs

Localization glossary packs are KB packs whose SQLite store includes
`glossary_entries` and `glossary_aliases`. They feed `bgs-translator` RAG so an
LLM receives canonical terms such as places, factions, item names, UI concepts,
and do-not-translate entries. Put this guidance here, not in
`using-bgs-translator`, because the same maintenance rules apply to official,
mod-specific, and third-party glossary packs.

Official bundled policy:

- `bgs-l10n-starfield-zhhans` is the only official zh-Hans glossary pack we
  ship from vanilla game data because Starfield is the only supported BGS game
  with official Simplified Chinese localization.
- Do not fabricate official Skyrim/Fallout4 Chinese packs. If the user wants
  them, create third-party/user packs with explicit source, license, scope, and
  review notes.
- The Starfield official pack is large and should be distributed through KB
  Release artifacts, not copied into the portable plugin tree.

For a mod-specific translator KB, prefer a user namespace such as
`user-l10n-<game>-<mod>-zhcn`. Include only the mod's accepted terminology,
character/place names, recurring UI labels, and do-not-translate terms. Do not
dump every translated sentence into a term KB unless the user explicitly wants a
translation-memory style pack and accepts the recall/noise tradeoff.

For a third-party game localization KB, require:

- source language, target language, game, source project/version, and license;
- provenance in `bgs-kb-meta.yml` and in generated notes;
- a stable pack id outside reserved `bgs-kb-*` official namespaces;
- a small sample query after registration to verify the pack is discoverable.

If the input is an xTranslator SST dictionary, the translator tool has a
one-shot builder that creates the glossary SQLite shape directly:

```powershell
# Build a user-maintained glossary pack from an SST dictionary.
py -3.12 tools\bgs-translator\bgs_translator\tools\xtranslator_sst_to_kb_pack.py `
  --input "D:\path\to\source_english_chinese.sst" `
  --output-dir "C:\my-kb-roots\user-l10n-skyrim-thirdparty-zhcn" `
  --pack-id user-l10n-skyrim-thirdparty-zhcn `
  --display-name "User Skyrim zh-CN Localization Glossary" `
  --game SkyrimSE `
  --source-lang en `
  --target-lang zh-cn
```

Then set `BGS_KB_USER_PACKS` to the parent root, restart/reconnect the MCP, and
query a known term. For translator-only packs, use `xtl`/translator glossary
smokes as the stronger check because `bgs_kb_query` only searches Markdown-style
records unless the MCP has been upgraded for glossary-table queries.

## Official KB release maintenance

For project maintainers cutting a KB Release, use the release staging script:

```powershell
# Rebuild source-record packs, verify prebuilt glossary packs, zip all packs,
# and write dist/kb-release/manifest-index.json.
pwsh scripts/build-kb-release.ps1 -Force
```

The script includes the generated Starfield zh-Hans glossary pack in the release
index but does not rebuild it from Markdown records. If `kb.sqlite` hash
verification fails, regenerate that pack from its approved source SST before
publishing. The script prints the exact `gh release create ...` command; review
the staged `manifest-index.json` before running that network-side publish.

## Version-pinning advice

Follow latest when the user wants current general guidance and accepts normal KB refresh cadence.

Pin a specific pack version when a modpack release, guide, benchmark, or reproducibility note depends on exact advice staying stable. Record the pin in the modpack dev-log or release docs.

If a new pack's `minPluginVersion` exceeds the installed plugin version, warn and stop. Do not auto-upgrade the plugin. Offer choices: update the plugin with user consent, keep the older pack version, or pin the previous version until the plugin can be upgraded.

KB cadence is independent of plugin cadence. A new KB pack can be consumed when `schemaVersion` and `minPluginVersion` are compatible; it does not automatically imply an xEdit or MO2 change.

## Health checks

Quick KB smoke after maintenance:

```text
bgs_kb_status({})
bgs_kb_query({ query: "plugins", maxResults: 3 })
```

Expected: at least one loaded pack, no unexpected collision / integrity warnings, and at least one query hit. If the target game is known, include the game filter, for example:

```text
bgs_kb_query({ query: "plugins", games: ["Fallout4"], maxResults: 3 })
```

For custom packs, query a term from one of the custom records and verify hits are tagged with the custom `packId`.

If maintenance touched MO2 or xEdit runtime state, also use the appropriate setup / xEdit skill checks. Do not treat KB health as proof of live load-order or plugin state.

## Anti-patterns + warnings

- Never write directly into Stock Game / vanilla game `Data`. Any game-local change goes through an MO2 mod overlay or overwrite surface.
- KB records are advisory. xEdit MCP readback remains authoritative for actual plugin, record, conflict, and load-order state.
- Do not use `BGS_KB_USER_PACKS` to point at a single pack directory; point it at a root containing pack directories.
- Do not use reserved `bgs-kb-*` pack IDs for local packs.
- Do not install or upgrade KB packs with a `minPluginVersion` the current plugin does not satisfy.
- Do not delete all old cache versions; keep current + previous unless the user explicitly chooses otherwise.

## Refreshing Nexus update state without opening MO2 (Option B)

Use this when the user wants fresh `newestVersion`, `nexusFileStatus`,
`lastNexusQuery`, and `lastNexusUpdate` metadata without opening MO2 and running
`Tools -> Check All for Updates`.

Why this exists: mobase's Python API does not expose the GUI update-check
trigger, and three of the four timestamp fields are not on the abstract
`IModInterface`. See KB record
`install-planning.nexus-direct-api-update-check.v1`. The direct Nexus API read
path works for both Free and Premium accounts; these read endpoints are not
Premium-gated.

Prerequisite: the user must already have Nexus auth configured in MO2. That same
MO2 credential store is the API-key source for the agent; see the next section.

Endpoints used:

```text
GET https://api.nexusmods.com/v1/games/{game_domain}/mods/updated.json?period=1m
GET https://api.nexusmods.com/v1/games/{game_domain}/mods/{id}.json
```

The first endpoint is one bulk call to discover recently updated mods. The
second endpoint is one per-mod call for fresh metadata. Nexus' rate budget is
20,000 calls/day; a full 300-mod refresh is about 301 calls and is comfortable.

Per-mod `meta.ini` update shape:

```powershell
$statusMap = @{ "published"=1; "hidden"=9; "removed"=6; "wastebinned"=6; "under_moderation"=9 }
$mod = Invoke-RestMethod -Uri "https://api.nexusmods.com/v1/games/starfield/mods/$modid.json" -Headers $headers
$statusInt = if ($statusMap.ContainsKey($mod.status)) { $statusMap[$mod.status] } else { 1 }
$nowIso = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$updatedIso = [DateTimeOffset]::FromUnixTimeSeconds($mod.updated_timestamp).ToString("yyyy-MM-ddTHH:mm:ssZ")
$content = [IO.File]::ReadAllText($metaPath, [Text.UTF8Encoding]::new($false))
$content = $content -replace '(?m)^newestVersion=.*$', "newestVersion=$($mod.version)"
$content = $content -replace '(?m)^nexusFileStatus=.*$', "nexusFileStatus=$statusInt"
$content = $content -replace '(?m)^lastNexusQuery=.*$', "lastNexusQuery=$nowIso"
$content = $content -replace '(?m)^lastNexusUpdate=.*$', "lastNexusUpdate=$updatedIso"
[IO.File]::WriteAllText($metaPath, $content, [Text.UTF8Encoding]::new($false))
```

For production-grade automation, prefer the helper script:

```powershell
pwsh scripts\refresh-nexus-update-state.ps1 -MO2Root <path> -Game starfield
```

Caveat: direct `meta.ini` writes do not refresh MO2's in-memory
`ModInfoRegular` until the next `organizer.refresh()` or MO2 restart.

## Reading Nexus credentials from MO2's Windows Credential Manager store

MO2 stores Nexus credentials globally for the current Windows user, not per MO2
instance. All portable MO2 instances under the same Windows account share them.
MO2 uses `getWindowsCredential` / `setWindowsCredential` in `settings.cpp`.

Credential Manager targets:

| Target | Meaning |
|---|---|
| `ModOrganizer2_APIKEY` | Legacy 162-character personal API key. |
| `ModOrganizer2_NEXUS_OAUTH_TOKENS` | Compact JSON `{access_token, refresh_token, expires_at, scope, token_type}` from the modern OAuth flow. |

Read pattern:

```powershell
$signature = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class CredMan {
  [DllImport("advapi32.dll", SetLastError=true, EntryPoint="CredReadW", CharSet=CharSet.Unicode)]
  static extern bool CredRead(string target, uint type, uint flag, out IntPtr cred);
  [DllImport("advapi32.dll")] static extern void CredFree(IntPtr p);
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
  public struct CREDENTIAL { public uint Flags,Type; public IntPtr TargetName,Comment; public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten; public uint CredentialBlobSize; public IntPtr CredentialBlob; public uint Persist,AttributeCount; public IntPtr Attributes,TargetAlias,UserName; }
  public static string Read(string t) { IntPtr p; if (!CredRead(t,1,0,out p)) return null; try { var c=(CREDENTIAL)Marshal.PtrToStructure(p,typeof(CREDENTIAL)); byte[] b=new byte[c.CredentialBlobSize]; Marshal.Copy(c.CredentialBlob,b,0,(int)c.CredentialBlobSize); int nz=0; for(int i=1;i<b.Length;i+=2)if(b[i]==0)nz++; return nz>(b.Length/4)?Encoding.Unicode.GetString(b):Encoding.UTF8.GetString(b); } finally { CredFree(p); } }
}
'@
Add-Type -TypeDefinition $signature -Language CSharp
$apiKey = [CredMan]::Read("ModOrganizer2_APIKEY")
$oauthJson = [CredMan]::Read("ModOrganizer2_NEXUS_OAUTH_TOKENS")
```

Verification call:

```powershell
Invoke-RestMethod -Uri "https://api.nexusmods.com/v1/users/validate.json" -Headers @{ APIKEY = $apiKey }
```

Expected fields include `user_id`, `name`, `is_premium`, and `is_supporter`.

[WARNING]
Reading user credentials requires explicit user consent. Mask the key in any
logged output, for example `d0Ra...72d4 (len=162)`. Recommend key rotation after
the session if there is any leak risk.

Failure modes:

- `cmdkey /list | findstr nexus` returns nothing because the target name has no
  `nexus` string. Use `cmdkey /list | findstr ModOrganizer2` instead.
- HKCU registry entries such as `HideCreateInstanceIntro` are cosmetic flags,
  not credentials.
- `ModOrganizer.ini` `[Settings]` has no auth fields.
- If `CredRead` returns null, Nexus auth is not set up in MO2 yet. Direct the
  user to `Settings -> Nexus -> Connect to Nexus`.

See KB record `install-planning.mo2-windows-credential-mining.v1`.

## Script Extender (xSE) update workflow — game-root drop, runtime-pinned

Use this when Steam updates the game runtime and the existing xSE DLL no longer
matches it. The signal is a launch refusal through the xSE loader because the
DLL runtime tag does not match the current `<game>.exe` `FileVersion`.

Detection:

```powershell
# Current xSE version (filename pattern)
Get-ChildItem "$gameRoot\sfse_*.dll" | Select Name  # e.g. sfse_1_15_222.dll = SFSE for runtime 1.15.222

# Current Steam runtime
(Get-Item "$gameRoot\Starfield.exe").VersionInfo.FileVersion  # e.g. 1.16.244.0

# If they do not match, update is needed.
```

Latest-version sources: silverlock.org points to Nexus mod `#106` for SFSE,
`#100216` for SKSE64, and `#42147` for F4SE.

Update workflow:

1. Get the latest `file_id` from
   `/v1/games/{game}/mods/{xse_mod_id}/files.json`; use the file with
   `category_name=MAIN`.
2. Premium: call
   `POST /v1/games/{game}/mods/{xse_mod_id}/files/{file_id}/download_link.json`.
   The response is an array of seven CDN mirrors (Chicago, Amsterdam, Prague,
   LA, Miami, Dallas, plus Nexus CDN). Pick the first URL.
3. Free: open the Nexus page in a browser, click manual download, and save the
   `.7z` to a known location.
4. Extract the `.7z`. Gotcha: the archive expands to an `<xse>_<version>/`
   subdirectory, such as `sfse_0_2_21/`, not a flat folder. Glob-find files:
   `Get-ChildItem -Recurse -Filter "sfse_*.dll" | Select-Object -First 1`.
5. Backup current game-root xSE files to
   `<MO2_Root>\.backups\sfse-<oldver>_pre-<newver>-update_<timestamp>\`.
6. Copy the new DLL, readme, and whatsnew files to the game root. Skip files
   with unchanged sha256; the `<xse>_loader.exe` often does not change between
   minor versions.
7. Delete the old runtime DLL. This is optional but recommended for cleanliness;
   the loader auto-picks by runtime match and does not need the old DLL.
8. Verify sha256 for all four game-root files against staging.

[WARNING]
This writes to the real game install, for example
`D:\SteamLibrary\steamapps\common\<game>\`. It requires explicit per-session
user confirmation. xSE has no MO2 VFS overlay path: the loader must spawn
`<game>.exe`, so it has to live next to it.

For production-grade automation:

```powershell
pwsh scripts\install-xse-update.ps1 -GameRoot <path> -XseMod sfse|skse|f4se|nvse
```

See KB record `engine.xse-update-workflow.v1`.

## See also

- `setting-up-bgs-modding-environment` — first-run MO2 / xEdit / KB acquisition orchestrator.
- `using-bgs-modding-superpowers` — session bootstrap, available tools, and hard BGS modding rules.
- `docs/internal/roadmap.md` — KB track status and phase closeouts.
- Deep reference: `docs/internal/superpowers/specs/2026-06-02-agentic-cross-game-kb-design.md`.
