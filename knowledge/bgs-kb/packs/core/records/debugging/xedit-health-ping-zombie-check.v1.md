---
id: debugging.xedit-health-ping-zombie-check.v1
title: xedit_health uses system.ping to catch zombie daemon state
domains: [debugging, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A ready-looking xEdit daemon still needs a health ping; xedit_health sends system.ping so agents can distinguish a responsive daemon from stale lifecycle state.
  confidence: verified-project-doc
queryKeys: [xedit_health, system.ping, zombie daemon, responsive true]
severity: high
sources:
  - kind: project-skill
    ref: skills/setting-up-bgs-modding-environment/SKILL.md
    sectionPath: Verify with a semantic smoke test
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: system.* commands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xedit_health uses system.ping to catch zombie daemon state

Lifecycle state can be stale if a process died or a pipe became unresponsive.
The health check closes that gap by sending a real `system.ping` through the daemon transport.

Agents should use health after readiness before trusting domain tools for semantic work.
If health is not responsive, report the lifecycle mismatch instead of continuing as if xEdit is available.

This is the difference between a process table entry and an agent-ready automation daemon.
