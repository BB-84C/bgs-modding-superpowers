---
id: tooling-mo2.xedit-daemon-readiness-window.v1
title: xEdit automation readiness can take 60 to 240 seconds on launch
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: xEdit daemon startup can legitimately take minutes while loading the active plugin set, so lifecycle tools should poll status rather than assuming a 30-second readiness timeout is enough.
  confidence: verified-project-doc
queryKeys: [xedit readiness, 240 seconds, startup timeout, xedit_status]
severity: high
sources:
  - kind: project-skill
    ref: skills/setting-up-bgs-modding-environment/SKILL.md
    sectionPath: Verify with a semantic smoke test
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout / Now known
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit automation readiness can take 60 to 240 seconds on launch

First launch can be slow because xEdit is parsing the active load order.
A process that is still starting is not automatically a zombie or a failed harness.

Use non-blocking lifecycle: start once, poll `xedit_status` with reasonable sleeps, then confirm with health when ready.
If status reports failed, surface the error exactly instead of continuing to poll.

This record exists because the previous 30-second readiness assumption produced false failures.
