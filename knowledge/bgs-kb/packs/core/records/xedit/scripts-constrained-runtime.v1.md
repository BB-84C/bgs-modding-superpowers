---
id: xedit.scripts-constrained-runtime.v1
title: xEdit Pascal scripts run without shell, UI, clipboard, process spawn, or filesystem write access
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "The xEdit automation script runtime is deliberately constrained: filesystem reads are allowed, but filesystem writes, UI, shell, clipboard, process-spawn, and external declarations are denied."
  confidence: verified-project-doc
queryKeys: [Pascal script runtime, external declarations, runtimeFsWrite, clipboard, process spawn]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Mutation policy
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit Pascal scripts run without shell, UI, clipboard, process spawn, or filesystem write access

Automation scripts are for in-daemon operations, not arbitrary machine automation.
The constrained runtime allows reads but denies filesystem writes and common escape hatches such as UI calls, shell/process spawning, clipboard access, and external declarations.

Agents should design scripts around xEdit operations and return structured findings through the daemon.
If a task needs host-file output, use the MCP or CLI layer outside the Pascal runner.

This boundary is part of the safety model for letting agents compose scripts.
