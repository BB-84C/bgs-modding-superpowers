---
id: tooling-mo2.xedit-client-subcommand-surface.v1
title: xedit-client.ps1 exposes process launch/status/wait/stop and automation call
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The verified xedit-client.ps1 surface has process launch, status, wait, stop groups plus automation call, whose call flags include xedit-pid, request-file, response-file, and timeout-seconds.
  confidence: verified-project-doc
queryKeys: [xedit-client.ps1, process launch, automation call, xedit-pid, request-file]
severity: medium
sources:
  - kind: project-internal-doc
    ref: AGENTS.md
    sectionPath: Updates (2026-05-30) — launch discipline + xedit-client.ps1 surface
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xedit-client.ps1 exposes process launch/status/wait/stop and automation call

The client surface has already been discovered and codified.
Agents should not spend another session re-deriving its subcommand groups or automation-call flags.

Use `process launch/status/wait/stop` for process lifecycle and `automation call` for a request/response exchange against a known xEdit PID.
The automation call needs request and response file paths plus a timeout.

This record is mainly for recovering from stale assumptions about the outer client shape.
