---
id: tooling-mo2.opencode-vfs-launcher-programmable-entrypoint.v1
title: OpenCodeVfsLauncher is the programmable MO2 child-process entrypoint
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: OpenCodeVfsLauncher is the MO2-internal programmable bootstrap for dynamic target paths, target arguments, state files, wait modes, transport modes, and child PID capture.
  confidence: verified-project-doc
queryKeys: [OpenCodeVfsLauncher, programmable entrypoint, child PID, target args, MO2 run]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/memory/40-mo2-launcher-architecture.md
    sectionPath: Rules
  - kind: project-internal-doc
    ref: AGENTS.md
    sectionPath: Updates (2026-05-30)
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OpenCodeVfsLauncher is the programmable MO2 child-process entrypoint

The programmable entrypoint exists for runs that need per-call launch detail.
It still goes through `ModOrganizer.exe`; host-shell helper invocation is not the same thing as an MO2 VFS launch.

Use this path when the harness needs dynamic target args, state files, wait modes, or direct child-process state.
That keeps xEdit inside the MO2-projected environment while still giving agents structured launch control.

Compare what xEdit actually sees before declaring two launch paths equivalent.
