---
id: xedit.formid-prefix-stripping.v1
title: xEdit daemon rejects FormIDs with 0x prefix
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The xEdit automation daemon expects bare hexadecimal FormIDs and rejects values with a 0x prefix; the MCP accepts either form and strips the prefix before forwarding.
  confidence: verified-project-doc
queryKeys: [FormID prefix, 0x FormID, bare hex FormID, formId normalization]
severity: medium
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit daemon rejects FormIDs with 0x prefix

The automation daemon wants load-order-resolved FormIDs as bare hexadecimal text.
Agent-facing tools may still accept `0x0000003C` because that is a common way to write a FormID in code and logs.

The boundary is the MCP edge: normalize once before calling the daemon, then keep the daemon request shape stable.
Do not push prefix handling down into every record-side tool.

If a daemon call fails on an otherwise valid record id, check whether the request crossed the MCP edge or bypassed its normalization.
