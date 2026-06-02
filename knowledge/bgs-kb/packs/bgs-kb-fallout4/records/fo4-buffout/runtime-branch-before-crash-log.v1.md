---
id: fo4-buffout.runtime-branch-before-crash-log.v1
title: Check the Fallout 4 runtime branch before interpreting Buffout logs
domains: [debugging, version-differences]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A crash log from a mismatched Fallout 4 runtime/F4SE branch can mislead triage, so confirm the executable version and extender build first.
  confidence: verified-official
queryKeys: [F4SE 1.10.163, F4SE 1.10.984, runtime mismatch, Buffout crash log]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
related: [engine.xse-plugin-version-compatibility.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Check the Fallout 4 runtime branch before interpreting Buffout logs

F4SE publishes different builds for different Fallout 4 runtimes, including older and next-gen branches.
If a modpack mixes old-runtime DLLs with a newer executable, the crash may originate before game content matters.

Record the runtime and F4SE versions in every crash-log triage note.
Only then classify record conflicts, BA2 issues, ENB injection, or plugin load failures.
