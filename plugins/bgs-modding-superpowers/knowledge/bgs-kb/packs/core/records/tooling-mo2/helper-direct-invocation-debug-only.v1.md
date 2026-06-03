---
id: tooling-mo2.helper-direct-invocation-debug-only.v1
title: MO2 launcher helper scripts are debug-only unless MO2 activation is proven
domains: [debugging, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: mo2-vfs-launcher helper scripts are the implementation behind an MO2 entrypoint, not a standalone replacement for MO2 activation from the host shell.
  confidence: verified-project-doc
queryKeys: [mo2-vfs-launcher.ps1, helper direct, MO2 activation, debug path]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/memory/40-mo2-launcher-architecture.md
    sectionPath: Rules
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# MO2 launcher helper scripts are debug-only unless MO2 activation is proven

The helper script is the execution body behind the configured MO2 tool.
Running it directly from the host shell does not by itself activate MO2's VFS or profile state.

Direct helper invocation is acceptable for debugging internals only when the session has already proved equivalent runtime state.
Otherwise, use the MO2 entrypoint and verify the loaded profile, plugins, and VFS projection.

This record prevents agents from collapsing the launcher architecture back into a standalone script.
