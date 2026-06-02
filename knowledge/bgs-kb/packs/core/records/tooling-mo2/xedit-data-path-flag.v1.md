---
id: tooling-mo2.xedit-data-path-flag.v1
title: "xEdit -D: data-path flag overrides registry-discovered Steam install"
domains: [xedit, load-order, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "Agent-launched xEdit should receive an explicit dataPath derived from MO2 gamePath plus Data, because the -D: flag prevents xEdit from falling back to a registry-discovered platform install."
  confidence: verified-project-doc
queryKeys: ["-D:", dataPath, gamePath, MO2 Data, registry-discovered install, wrong Data]
severity: critical
sources:
  - kind: project-internal-doc
    ref: AGENTS.md
    sectionPath: Updates (2026-05-30) — launch discipline + xedit-client.ps1 surface
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout / Now known
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit -D: data-path flag overrides registry-discovered Steam install

In an MO2-backed harness, the Data directory xEdit should see is derived from MO2's `gamePath`, then suffixed with `\Data`.
Passing that path as `dataPath` maps to xEdit's `-D:` flag and keeps the runtime pointed at the managed game root.

Without the explicit override, xEdit may discover the platform install through the Windows registry and inspect the wrong Data tree.
That produces harness drift: wrong plugins, wrong masters, and misleading conflict evidence.

Agents should treat `dataPath` as part of the launch contract whenever they start or restart xEdit for MO2-projected work.
