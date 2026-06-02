---
id: xedit.error-invalid-request.v1
title: invalid_request means fix the daemon request shape
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: invalid_request is a transport or validation failure, usually caused by a malformed envelope, wrong args object shape, unsupported field, or bad locator formatting.
  confidence: verified-project-doc
queryKeys: [invalid_request, request validation, malformed envelope, args object]
severity: medium
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Error code reference
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# invalid_request means fix the daemon request shape

When `error.code` is `invalid_request`, debug the request before debugging the plugin.
Common causes are scalar `args`, a missing locator field, a `0x` prefix that bypassed MCP normalization, or a command-specific field with the wrong type.

Recovery is to validate and resend the request through the MCP adapter.
Do not relaunch xEdit or reorder plugins until the envelope has been inspected.

This code should be handled as client input repair, not daemon instability.
