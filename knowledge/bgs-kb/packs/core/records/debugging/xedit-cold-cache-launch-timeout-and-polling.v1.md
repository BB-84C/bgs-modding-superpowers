---
id: debugging.xedit-cold-cache-launch-timeout-and-polling.v1
title: First-launch cold-cache xEdit takes 9+ minutes on real load orders; 240s daemon timeout and aggressive polling will both break it
kind: rule
domains: [debugging, xedit, engine]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: After any xEdit binary swap or cache invalidation, the FIRST launch must rebuild the .refcache from scratch. On a 175-plugin Starfield profile this takes 9-10 minutes of wall-clock time. The current xedit-mcp `xedit-client.ps1` has a 240-second timeout for daemon readiness — first-launch cache-cold WILL exceed this and the daemon will be reported as failed even though xEdit is still parsing. Additionally, `xedit_status` polling during cold-cache build is NOT free; the daemon's status handler runs on the same Pascal thread as the parser, and aggressive polling (30s cadence) has been observed to stall or crash xEdit's parser mid-build. Recommended pattern is to build the cache via manual GUI launch first (through MO2's normal launch path or `Mo2Mo2RunTool_tool`), then use the daemon against the warm cache (~3 min wall-clock).
  confidence: high
queryKeys:
  - xEdit first launch timeout
  - cold cache 9 minutes
  - 240 second timeout
  - xedit_status polling during build
  - xEdit parser stall
  - xedit-client.ps1 timeout
  - xEdit daemon readiness timeout
  - cache rebuild time
  - daemon launch fails after binary swap
  - xEdit parse hang
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-27 xEdit pre-flight on 175-plugin Starfield BB84自用2 profile; 9:45 manual cold launch + 240s daemon timeout abort + parse stall correlation with 30s polling cadence
related:
  - engine.xedit-binary-cache-lifecycle.v1
  - xedit-contrib-build-vs-release-channel.v1
  - tooling-mo2.xedit-daemon-readiness-window.v1
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# First-launch cold-cache xEdit takes 9+ minutes on real load orders; 240s daemon timeout and aggressive polling will both break it

## Perspective: OBJECTIVE

## The cold-cache launch timing

Empirical measurement, BB84's Starfield MO2 BB84自用2 profile (175 plugins enabled), 2026-06-27:

| Launch type | Wall-clock time |
|---|---|
| First launch after binary swap (cache built from scratch) | **9 minutes 45 seconds** (manual GUI launch) |
| Subsequent launch with warm cache | **~2 minutes 56 seconds** (daemon launch) |

Cache build time scales with:
- Number of plugins in the load order (175 → ~10 min; smaller profiles proportionally faster)
- Size of each plugin (large overhauls cost more parsing time)
- Disk speed (SSD assumed; HDD multiplies the time significantly)
- CPU single-thread performance (xEdit's parser is largely single-threaded)

Estimate: budget ~3 seconds per plugin on a typical SSD + modern CPU for cache-cold parsing. A 100-plugin profile is ~5 minutes; a 200-plugin profile is ~10 minutes; a 300-plugin profile is ~15 minutes.

## The 240-second timeout problem

The xedit-mcp's `tools/mo2-vfs-launcher/xedit-client.ps1` ships with a hard-coded 240-second timeout for daemon readiness. When `xedit_start` is invoked and the cache is cold, the daemon will not respond to readiness probes within 240s — it's still parsing. The MCP correctly cleans up the PID and reports `status: "failed"` with the message:

> Timed out waiting for native xEdit automation readiness after 240s. xEdit may still be parsing the load order; consider bumping the timeout further if your profile is large.

This is a known limitation, not a bug. The agent must work around it.

## The polling interference problem

During cold-cache build, `xedit_status` is not a free read. The daemon's status response handler runs on xEdit's main Pascal thread, which is also where the parser is working. Empirical 2026-06-27 observation: `xedit_status` polled at 30-second cadence during cold-cache build correlated with a parser stall requiring manual process kill (~3:18 elapsed, daemon reported "starting" with internal elapsedSeconds way behind wall clock).

The correlation may or may not be causal — could be coincidence — but the safer pattern is to assume polling is not free and stay quiet.

## Recommended workflow patterns

### Pattern A: build cache via manual GUI launch first (RECOMMENDED for current tooling)

```
1. Check cache state: <MO2_Root>/overwrite/<Game>Edit Cache/ either missing or .stale-* renamed
2. Launch xEdit through MO2's normal launch path:
   - Via Mo2Mo2RunTool_tool with the configured customExecutable (e.g. title="SF1Edit64")
   - OR user clicks the MO2 GUI button
   - OR Start-Process the binary directly with -wait
3. Wait for xEdit's loading window to settle (status bar shows "Background Loader: finished" + UI is interactive)
4. Close xEdit cleanly (File > Exit, or just close the window)
5. Verify cache rebuilt: ls <MO2_Root>/overwrite/<Game>Edit Cache/ has N files for N plugins
6. NOW use xedit_start to launch the daemon against the warm cache (~3 min)
```

This sidesteps the 240s timeout and the polling-interference risk entirely.

### Pattern B: bump the timeout in xedit-client.ps1

If automated cold-cache builds are required and manual GUI launch is undesirable, modify the xedit-client.ps1 timeout constant. This is a tooling change that lives in the xedit-mcp source, not a runtime config — coordinate with the xedit-mcp owner before changing.

### Pattern C: poll less aggressively

If pattern A is not available and pattern B is not approved, the fallback is to fire `xedit_start`, wait quietly for 8+ minutes without polling, then check once. This avoids the polling-interference risk but still hits the 240s timeout — so the agent must understand that "failed" status from xedit-mcp does not necessarily mean xEdit has actually died. Cross-check with `Get-Process xEdit*` to see if the process is still alive and working.

## Polling discipline summary

| Phase | Poll cadence |
|---|---|
| Cold-cache build (first launch post-swap, ~9 min budget) | Do not poll, or poll once at 8+ min elapsed |
| Cache-warm launch (~3 min budget) | 60s cadence is fine |
| Steady state (status: ready) | Free; domain tools (`xedit_session`, `xedit_health`, `xedit_call`) can be called freely |

## Operational notes

- Daemon-reported `elapsedSeconds` is NOT wall-clock from xedit_start. It appears to count from "daemon ready to receive probes," which is well into the parse. A 60-second wall-clock can show as `elapsedSeconds: 10`. Don't try to predict ready time from this.
- After `status: ready`, the daemon is fully responsive; the cache-cold period is behind you.
- `xedit_stop` on a clean dirty state preserves the cache. `xedit_start` immediately after will hit warm cache.
- If the user reports "xEdit hangs forever on first launch," ask if they did a binary swap. The 9-minute cache build looks like a hang to anyone who hasn't seen it before.

## See also

- `engine.xedit-binary-cache-lifecycle.v1` — the binary-cache binding that makes cold rebuilds necessary.
- `xedit-contrib-build-vs-release-channel.v1` — choosing what binary to deploy in the first place.
- `tooling-mo2.xedit-daemon-readiness-window.v1` — sibling readiness-timing guidance for the steady-state daemon.
