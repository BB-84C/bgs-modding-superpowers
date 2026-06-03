---
id: xedit.scripts-agent-namespace-only.v1
title: xEdit automation scripts are writable only under the Agent namespace
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The scripts.write surface is intentionally scoped to the Agent namespace, so agents should not overwrite arbitrary user or tool scripts.
  confidence: verified-project-doc
queryKeys: [scripts.write, Agent namespace, Pascal script, script storage]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: scripts.* commands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit automation scripts are writable only under the Agent namespace

The automation script surface has a constrained writable namespace.
Agents can author scripts under `Agent/`, but should not modify the user's broader xEdit script collection.

This keeps generated automation separate from curated user tooling and makes cleanup/audit simpler.
If a workflow needs a reusable script, promote it deliberately rather than writing into arbitrary paths.

Treat namespace refusal as a guardrail, not a blocker to route around.
