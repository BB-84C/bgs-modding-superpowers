---
id: xedit.branch-on-error-code.v1
title: Branch on xEdit daemon error.code, not prose messages
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: xEdit failure envelopes expose a stable error.code; recovery logic must branch on that code rather than matching the human-readable message text.
  confidence: verified-project-doc
queryKeys: [error.code, daemon error, invalid_request, prose message]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Daemon protocol essentials
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Branch on xEdit daemon error.code, not prose messages

The daemon's error message is for people; `error.code` is for programs.
Message text can change as diagnostics improve, but a stable code can drive recovery paths and tests.

Agents should map known codes to specific next actions, such as fixing a malformed request or checking load-order state.
Do not use substring checks against the prose message as a rule system.

This is especially important for small models that otherwise overfit to one example failure string.
