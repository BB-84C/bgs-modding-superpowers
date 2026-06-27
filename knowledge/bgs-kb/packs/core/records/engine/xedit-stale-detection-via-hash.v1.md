---
id: engine.xedit-stale-detection-via-hash.v1
title: Detect stale xEdit binaries by SHA-256 comparison against the reference source, not by Version.FileVersion
kind: rule
domains: [engine, xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: PowerShell's `Get-Item.VersionInfo.FileVersion` is not a reliable staleness signal for xEdit because the contrib fork ships multiple builds under the same labelled version (4.1.5.0, 4.1.6, etc.) as continuous releases evolve. Two binaries with identical FileVersion strings can differ by megabytes and tens of contract-feature commits. The canonical staleness test is SHA-256 against the chosen reference source — either `D:\TES5Edit-contrib\Build\xEdit64.exe` for developers tracking the contrib fork, or the file returned by `fetch-xedit-release.ps1` for end-user release-channel installs. Surface both the hash mismatch AND the mtime gap so a human reader can quickly judge whether the drift is real or a build-metadata artifact.
  confidence: high
queryKeys:
  - xEdit stale detection
  - xEdit binary hash compare
  - SHA-256 vs FileVersion
  - xEdit version comparison reliability
  - is my xEdit stale
  - detect xEdit upgrade needed
  - xEdit contrib build hash
  - Get-FileHash for xEdit
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-27 xEdit pre-flight (file version 4.1.5.0 reported for both binaries, but SHA-256 + mtime + size all differed)
related:
  - engine.xedit-binary-cache-lifecycle.v1
  - xedit-contrib-build-vs-release-channel.v1
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# Detect stale xEdit binaries by SHA-256 comparison against the reference source, not by Version.FileVersion

## Perspective: OBJECTIVE

## Why FileVersion is unreliable for xEdit

xEdit is a Delphi-built tool. The `VersionInfo` resource (which `Get-Item.VersionInfo.FileVersion` reads) is set at build time in the `.dpr` project options. The contrib fork's release cadence often holds the labelled version steady (e.g. `4.1.5.0` across an entire phase, `4.1.6` for the next phase) while shipping continuous binary changes — bug fixes, new contract features, parser updates. Two binaries can be 10 days apart in build time, megabytes apart in size, and tens of commits apart in functionality, yet report the same `4.1.5.0` to PowerShell.

Concrete 2026-06-27 case from BB84's Starfield MO2:

| Binary | FileVersion | Size | SHA-256 (head) | mtime |
|---|---|---|---|---|
| MO2's deployed SF1Edit64.exe | 4.1.5.0 | 55,264,879 | E125D7363A107BA5... | 2026-06-07 |
| Contrib Build/xEdit64.exe | 4.1.5.0 | 55,429,570 | F878655D87F53E1C... | 2026-06-17 |

Same FileVersion. Different hash, different size, 10 days apart. The contrib build includes contract 0.18 / 0.19 / 0.20 (WRLD parent support, reverse navigation, multi-pattern OR filters). The deployed binary doesn't. A staleness check that only compared FileVersion would have missed this.

## The canonical detection pattern

```powershell
function Test-XEditStale {
  param([string]$Mo2Binary, [string]$ReferenceBinary)
  $mo2Hash = (Get-FileHash -LiteralPath $Mo2Binary -Algorithm SHA256).Hash
  $refHash = (Get-FileHash -LiteralPath $ReferenceBinary -Algorithm SHA256).Hash
  $mo2Mtime = (Get-Item -LiteralPath $Mo2Binary).LastWriteTime
  $refMtime = (Get-Item -LiteralPath $ReferenceBinary).LastWriteTime
  $stale = $mo2Hash -ne $refHash
  return [pscustomobject]@{
    Stale       = $stale
    Mo2Hash     = $mo2Hash.Substring(0, 16) + '...'
    RefHash     = $refHash.Substring(0, 16) + '...'
    Mo2Mtime    = $mo2Mtime
    RefMtime    = $refMtime
    GapDays     = ($refMtime - $mo2Mtime).Days
  }
}
```

Run against the canonical reference source for the environment (see the contrib-vs-release-channel record). Surface the result to a human reader along with the mtime gap — a 10-day gap + hash mismatch is real drift; a 1-day gap + hash mismatch may just be a rebuild without semantic changes.

## What counts as "stale enough to upgrade"

This rule deliberately does not prescribe a single threshold. The signal is hash mismatch; the decision is contextual:

- **No hash mismatch**: not stale, no action.
- **Hash mismatch + recent reference (days, not weeks)**: usually a minor rebuild; check contrib commit log for whether the changes affect work in flight.
- **Hash mismatch + reference 1+ weeks newer**: likely contains real feature or fix changes; surface as a recommended upgrade.
- **Hash mismatch + reference older than deployed**: reverse drift — someone deployed a newer binary than the reference source has. Investigate before swapping; the reference source may itself be stale.

For agentic decision-making, default to "surface the hash mismatch + mtime gap and let the orchestrator/user decide" rather than auto-upgrading on any mismatch.

## What about the HookBridge.dll

Same SHA-256 method, against the plugin-tree source:

```powershell
$mo2Dll  = "<MO2_Root>\tools\xEdit\xEditHookBridge.dll"
$refDll  = "<plugin>\tools\xedit-hook-bridge\dist\xEditHookBridge.dll"
```

The HookBridge ships with this plugin (NOT the xEdit fork), so its reference source is always the plugin tree — never the contrib build dir. Hash mismatch → run `install-xedit-hook-bridge.ps1`. Same-hash → no action.

## Anti-patterns

- Comparing only FileVersion strings and concluding "same version, no upgrade needed". False negative; the binaries can differ on contract features.
- Comparing only file size. Size catches obvious mismatches but a small commit can leave size unchanged while breaking ABI.
- Comparing only mtime. mtime catches recency but not content; a `touch` would defeat this.
- Auto-upgrading on any hash mismatch without surfacing the mtime gap. The orchestrator/user needs the time context to judge whether to take the upgrade.

## See also

- `engine.xedit-binary-cache-lifecycle.v1` — what to do after deciding the binary IS stale (cache invalidation is mandatory).
- `xedit-contrib-build-vs-release-channel.v1` — choosing which reference source to compare against.
