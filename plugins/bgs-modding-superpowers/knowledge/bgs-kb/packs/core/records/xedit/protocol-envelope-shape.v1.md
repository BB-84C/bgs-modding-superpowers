---
id: xedit.protocol-envelope-shape.v1
title: xEdit automation requests and responses use explicit envelopes
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: xEdit automation calls use a request envelope with command and args, and responses return either an ok result object or an error object with a stable code.
  confidence: verified-project-doc
queryKeys: [daemon protocol, request envelope, response envelope, command args]
severity: medium
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Daemon protocol essentials
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit automation requests and responses use explicit envelopes

The automation transport is not a loose command string interface.
Each request names a daemon command and passes an `args` object; each response is either an ok envelope with `result` or a failure envelope with `error`.

Agents should preserve that envelope shape through adapters and tests.
It keeps command routing, audit logs, and recovery logic independent of human-readable messages.

When adding a new MCP tool, shape validation should happen before the request crosses into the daemon.
