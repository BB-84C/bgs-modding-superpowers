---
id: xedit.contrib-build-vs-release-channel.v1
title: Choose xEdit binary source by user role — contrib build for developers, GitHub release for end users
kind: rule
domains: [xedit, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Two reference sources exist for the agent-friendly xEdit binary. (1) Local contrib dev build at `D:\TES5Edit-contrib\Build\` (or wherever the developer's TES5Edit-contrib checkout lives) — continuously rebuilt during fork development, captures unreleased contract features and fixes. (2) GitHub release artifacts fetched via the plugin's `scripts/fetch-xedit-release.ps1` from `BB-84C/TES5Edit` — tagged stable releases with reproducible manifests. For developers working on the xEdit fork or needing latest contract features (current contract 0.20 adds WRLD parent, reverse navigation, multi-pattern OR), use the contrib build. For end-user installs, reproducible modpack chains, or any scenario where the user is not authoring the binary, use the release channel. When ambiguous (deployed install, third-party support), ask which source the user wants before swapping.
  confidence: high
queryKeys:
  - xEdit reference source
  - contrib build vs release
  - TES5Edit-contrib local build
  - fetch-xedit-release.ps1
  - where to get xEdit binary
  - xEdit upgrade source
  - developer vs end-user xEdit
  - BB-84C TES5Edit release
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-27 xEdit pre-flight — contrib Build/xEdit64.exe at 4.1.6 r6 contains contract 0.18-0.20 additions, GitHub release stream typically lags by 1-2 phases
related:
  - engine.xedit-stale-detection-via-hash.v1
  - engine.xedit-binary-cache-lifecycle.v1
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# Choose xEdit binary source by user role — contrib build for developers, GitHub release for end users

## Perspective: SUBJECTIVE (selection strategy with objective grounding on what each source ships)

## The two sources

### Source 1: local contrib dev build

Path (BB84's machine): `D:\TES5Edit-contrib\Build\`. Other developer machines will have their own equivalent — the convention is `<contrib-checkout>/Build/` after running the Delphi build.

What it produces:
- `xEdit.exe` (32-bit)
- `xEdit64.exe` (64-bit)
- Possibly a fresh `xEditHookBridge.dll` if the developer is also iterating on the hook bridge

What ships:
- The current HEAD of the contrib fork's branch.
- Unreleased contract additions (currently 0.18 / 0.19 / 0.20: WRLD parent coords, reverse navigation, multi-pattern OR filters in `apply_filter`).
- Bug fixes not yet tagged into a release.
- Whatever WIP changes the developer hasn't committed to the release stream yet.

When to use:
- The user IS the contrib fork developer or a close collaborator.
- The work in flight needs a contract feature not yet in the latest release.
- An agentic skill being designed depends on a daemon command added in the last 1-2 weeks.
- The developer is doing semantic verification against a profile where the latest fixes matter.

### Source 2: GitHub release channel via `fetch-xedit-release.ps1`

Repo: `BB-84C/TES5Edit`. The plugin's `scripts/fetch-xedit-release.ps1` downloads the latest tagged release, verifies its sha256, and unpacks into `<MO2_Root>/tools/xEdit/`.

What it produces:
- Same binary set as the contrib build, but pinned to a specific tag.
- Accompanied by a release manifest with sha256s for reproducible installs.
- Tested in CI before tagging (release cadence is intentionally slower than contrib HEAD).

When to use:
- End-user install on a machine without a contrib checkout.
- Modpack distribution where the consumer needs reproducible build chains.
- Any third-party install path (`setting-up-bgs-modding-environment` Step 7 routes here by default).
- A version pin is required for a published modpack ("verified against xEdit X.Y.Z").

## Decision matrix

| User role | Preferred source |
|---|---|
| Contrib fork author | contrib build |
| Plugin author tracking contract additions | contrib build |
| End user installing per setup skill | release channel |
| Modpack curator pinning a tested version | release channel |
| Third-party agent on an unknown machine | release channel (and ASK before swapping) |

When the agent doesn't know the user role, surface both options before swapping. Default to release channel for safety.

## Versioning gotcha

Both sources may report the same `FileVersion` (e.g. `4.1.5.0`) for adjacent builds. Do not use FileVersion as the source-discriminator; use the path. The release-channel path is owned by `fetch-xedit-release.ps1` and lands in `<MO2_Root>/tools/xEdit/` along with a release manifest file. The contrib build path is whatever the developer's local Delphi build outputs.

See `engine.xedit-stale-detection-via-hash.v1` for the SHA-256 method that compares against either source.

## Operational pattern

```powershell
# Determine reference source by user role
if ($UserIsContribDev -or $NeedsUnreleasedFeatures) {
  $RefSource = "D:\TES5Edit-contrib\Build\xEdit64.exe"
} else {
  # Run the plugin script to get latest release; it returns the unpacked binary path
  & "<plugin>\scripts\fetch-xedit-release.ps1" -MO2Root $MO2_Root
  $RefSource = "$MO2_Root\tools\xEdit\xEdit64.exe"  # post-fetch state
}

# Compare deployed against reference
Test-XEditStale -Mo2Binary "$MO2_Root\tools\xEdit\SF1Edit64.exe" -ReferenceBinary $RefSource

# If stale, surface the gap and ask the orchestrator/user before swapping
```

## See also

- `engine.xedit-stale-detection-via-hash.v1` — SHA-256 comparison method.
- `engine.xedit-binary-cache-lifecycle.v1` — what happens after the swap (cache invalidation mandatory).
- `debugging.xedit-cold-cache-launch-timeout-and-polling.v1` — first-launch timing constraints after swap.
