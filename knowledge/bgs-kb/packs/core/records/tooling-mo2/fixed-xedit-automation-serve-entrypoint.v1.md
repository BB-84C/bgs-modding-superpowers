---
id: tooling-mo2.fixed-xedit-automation-serve-entrypoint.v1
title: OpenCode xEdit Automation Serve is the fixed MO2 xEdit daemon entrypoint
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: OpenCode xEdit Automation Serve is the preconfigured MO2 entrypoint for starting the xEdit automation daemon when no dynamic per-run argument plumbing is needed.
  confidence: verified-project-doc
queryKeys: [OpenCode xEdit Automation Serve, fixed entrypoint, MO2 tool, automation daemon]
severity: medium
sources:
  - kind: project-internal-doc
    ref: .opencode/memory/40-mo2-launcher-architecture.md
    sectionPath: Decision Guide
  - kind: project-internal-doc
    ref: AGENTS.md
    sectionPath: Updates (2026-05-30)
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OpenCode xEdit Automation Serve is the fixed MO2 xEdit daemon entrypoint

The fixed entrypoint is for the normal preconfigured automation-serve path.
It is useful when the harness does not need to inject a custom target path, state file, or per-run argument set.

Agents should not treat this as interchangeable with the programmable launcher.
Choose it when the stable MO2 tool definition already expresses the run.

When dynamic launch plumbing is required, use the OpenCodeVfsLauncher path instead.
