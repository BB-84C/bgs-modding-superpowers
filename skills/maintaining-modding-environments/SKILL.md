---
name: maintaining-modding-environments
description: "Use after first-run for ongoing modpack maintenance: log KB update, register custom pack, prune KB cache, modding environment health check, version pinning, or other recurring BGS modding environment care."
---

# Maintaining Modding Environments

## When to use

- The environment is already set up and the user asks to maintain, refresh, update, or health-check it.
- The user says "register custom pack", "install my KB pack", "set `BGS_KB_USER_PACKS`", or asks how to author a local KB pack.
- The user asks to check or apply knowledge-base updates after first-run.
- The user asks to prune the KB cache or clean old pack versions.
- The user asks whether to pin a KB pack version, follow latest, or handle a `minPluginVersion` warning.

## What this skill replaces

Use `setting-up-bgs-modding-environment` for first-run: MO2 detection, control-plane install, visible MO2 launch, first xEdit acquisition, first KB pack acquisition, and first semantic smoke.

This skill owns ongoing care after that first-run boundary: KB updates, cache hygiene, custom-pack authoring and registration, recurring environment health checks, and version-pinning advice.

## Check + apply KB updates

1. Start with `bgs_kb_status({})` to see loaded packs, versions, cache root, user roots, and warnings.
2. If `bgs_kb_check_updates` exists, call it for the installed pack IDs. Surface available updates, `breakingChange`, and release URLs before taking action.
3. If `bgs_kb_check_updates` is not present yet (pre-KB-6), check GitHub Releases for `bgs-modding-superpowers` KB pack artifacts and `manifest-index.json`. Do not invent release names.
4. Before installing or replacing a pack, get user consent for the download / cache mutation.
5. If `bgs_kb_install_pack` exists, use it with an exact `{ packId, version }`. Prefer `dryRun: true` before live install when the tool supports it.
6. If the install tool is not present yet, download the Release asset manually only after consent, verify the published sha256, extract into the cache layout below, then restart or reconnect the MCP so discovery runs again.
7. After any update, run the health checks below.

## Cache hygiene

Cache root on Windows:

```text
%LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/<packId>/<version>/
```

Each version directory contains `manifest.json`, `records/`, and `kb.sqlite`. Current policy: retain the current version and the immediately previous version as rollback/fallback. Prune versions older than that only after confirming the pack is not pinned by the user or referenced by a current modpack workflow.

Use the KB MCP CLI for routine pruning:

```powershell
node <plugin>\tools\bgs-kb-mcp\dist\cli.js prune-cache --dry-run
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
node <plugin>\tools\bgs-kb-mcp\dist\cli.js build <pack-root>
```

This produces `kb.sqlite` and `manifest.json` next to `records/`.

Validate and inspect:

```powershell
node <plugin>\tools\bgs-kb-mcp\dist\cli.js validate <pack-root>
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
$env:BGS_KB_USER_PACKS = "C:\my-kb-roots"
```

Do not set it to `C:\my-kb-roots\my-custom-pack`; that points at the pack itself and discovery will look one level too deep.

After registration, restart/reconnect the MCP so pack discovery runs, then call `bgs_kb_status({})` and verify the custom pack appears with the intended `packId`.

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

## See also

- `setting-up-bgs-modding-environment` — first-run MO2 / xEdit / KB acquisition orchestrator.
- `using-bgs-modding-superpowers` — session bootstrap, available tools, and hard BGS modding rules.
- `docs/internal/roadmap.md` — KB track status and phase closeouts.
- Deep reference: `docs/internal/superpowers/specs/2026-06-02-agentic-cross-game-kb-design.md`.
