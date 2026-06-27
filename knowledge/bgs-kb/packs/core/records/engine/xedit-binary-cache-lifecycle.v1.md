---
id: engine.xedit-binary-cache-lifecycle.v1
title: xEdit binary upgrades invalidate the .refcache cache and require deliberate cache cleanup
kind: rule
domains: [engine, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: xEdit caches parsed-plugin metadata to `<MO2_Root>/overwrite/<Game>Edit Cache/` as `.refcache` files keyed by load-order hash + per-plugin hash + locale tags. The cache is binary-version-bound — xEdit's record parser, contract version, and cache file format all evolve across releases, so a cache built by binary version A is unsafe to read with binary version B. Always move the cache dir aside (rename, do NOT delete) before the first launch after any binary swap, then let xEdit rebuild it. Stale caches produce subtle wrong-answer bugs that look like protocol errors but are actually parser-drift symptoms.
  confidence: high
queryKeys:
  - xEdit cache location
  - SF1Edit Cache directory
  - FO4Edit Cache directory
  - refcache file format
  - xEdit binary upgrade
  - cache invalidation after binary swap
  - xEdit cache rebuild
  - cache version binding
  - stale cache wrong answers
  - overwrite SF1Edit Cache
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-27 xEdit pre-flight (4.1.5 → 4.1.6 r6 swap on Starfield MO2)
related:
  - debugging.xedit-cold-cache-launch-timeout-and-polling.v1
  - xedit-contrib-build-vs-release-channel.v1
  - engine.xedit-stale-detection-via-hash.v1
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# xEdit binary upgrades invalidate the .refcache cache and require deliberate cache cleanup

## Perspective: OBJECTIVE

This rule is engine fact, not curator preference. The cache is owned by xEdit's parser; the binding between binary version and cache file is structural.

## Where the cache lives

For each game, xEdit writes its parsed-plugin metadata under MO2's overwrite directory:

| Game | Cache subdirectory |
|---|---|
| Skyrim (LE/SE/AE) | `<MO2_Root>/overwrite/SSEEdit Cache/` (or `TES5Edit Cache/` for LE) |
| Fallout 4 | `<MO2_Root>/overwrite/FO4Edit Cache/` |
| Fallout 3 / FNV | `<MO2_Root>/overwrite/FO3Edit Cache/` / `FNVEdit Cache/` |
| Starfield | `<MO2_Root>/overwrite/SF1Edit Cache/` |

File naming convention: `<load-order-hash>_<plugin-name>_<plugin-hash>_g<codepage>_t<codepage>_l<codepage>_<language>.refcache`. The leading hash is a deterministic digest of the active plugin set's master ordering; the per-plugin hash captures the plugin file's structural identity.

## Why the cache is binary-version-bound

Three independent concerns make cache-cross-version reuse unsafe:

1. **Record parser evolution**: xEdit's per-record parsing logic (CELL, REFR, NPC_, QUST, etc.) is updated across releases when new game patches change field shapes, when malformed-data tolerance improves, or when contract additions surface new sub-records. A cache file built under parser v1 may declare records that v2 would now parse differently.
2. **Contract version drift**: the daemon's automation contract (currently at `0.20` as of 4.1.6 r6) is what API consumers (mo2-mcp, agentic skills) target. Cache entries reference contract-level field shapes; a 0.20 daemon reading a 0.17-era cache will hit fields it expects to be present but aren't.
3. **Cache format itself**: the binary serialization of `.refcache` evolves. New versions may add tag bytes, alter integer widths, or extend record headers. xEdit reads cache files defensively but defensive reads are not guarantees.

The combined effect: a stale cache produces silently wrong reads. Wrong override winners, missing references, spurious itm/udr flags, hallucinated FormIDs. These are the worst class of bug because they look like correct protocol traffic.

## The mandatory upgrade pattern

```
1. Backup current tools/xEdit/ (binary-side rollback safety)
2. Swap binaries to new version
3. RENAME (do not delete) the existing <Game>Edit Cache/ to <Game>Edit Cache.stale-<timestamp>/
4. Launch xEdit (manual GUI first time, then daemon — see related cold-cache record)
5. Let it rebuild the cache (9-10 min on a 175-plugin Starfield profile)
6. Verify by reading a known record + checking conflict status
7. Keep the .stale-<timestamp>/ backup until the new cache is verified across multiple sessions
8. Cleanup the .stale-<timestamp>/ in a future maintenance pass
```

Step 3 is the load-bearing operation. Skipping it produces the silent-wrong-answer class of bug described above.

## When cache reuse IS safe

The cache is safe to keep across:

- Subsequent launches of the SAME binary version (this is the whole point of having a cache — first launch builds, subsequent launches reuse, 9 min → 3 min)
- MO2 profile switches IF the load order is unchanged (cache hashes include load order)
- xedit_stop / xedit_start cycles on the same binary
- Mo2Mo2RunTool launches of the configured xEdit customExecutable using the same binary

The cache is NOT safe across:

- Any binary version swap (the rule of this record)
- Game patches that change `<Game>.exe` `FileVersion` (sometimes new game versions ship plugin format tweaks that require parser updates)
- Cache directory copy from a different MO2 instance / profile / OS install

## Operational notes

- The cache dir can grow large (~100 MB for a 175-plugin profile). Do not include it in casual backups; it's deterministic from the load order + binary version.
- Disk space pressure: if cache + .stale backup is uncomfortable, delete the .stale backup AFTER verifying the new cache against at least one full session of audit work.
- Do NOT bake cache files into modpack distributions. They are environment-specific and tied to the consumer's exact MO2 layout.

## See also

- `debugging.xedit-cold-cache-launch-timeout-and-polling.v1` — the cold-cache-build timing window and the 240s daemon-readiness timeout gotcha.
- `xedit-contrib-build-vs-release-channel.v1` — choosing the right reference source for binary swap.
- `engine.xedit-stale-detection-via-hash.v1` — SHA-256 method for detecting stale binaries before deciding to swap.
