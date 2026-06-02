---
id: xedit.conflict-ca-itpo.v1
title: caITPO means identical to previous override
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "caITPO is xEdit's Identical To Previous Override condition: the record differs from the master chain somewhere, but this particular override contributes no new value beyond the preceding override."
  confidence: verified-project-doc
queryKeys: [caITPO, ITPO, identical to previous override, redundant override, conflict verdict]
severity: medium
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
  - kind: project-skill
    ref: skills/xedit-conflict-audit/SKILL.md
    sectionPath: Workflow
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# caITPO means identical to previous override

Map `caITPO` to the MCP verdict `itpo`.
It is weaker than a meaningful conflict because the current override is not changing the winning value relative to the previous override.

The right operator action is usually to surface it as cleanup/noise, not as a compatibility break.
However, it is not the same as `caITM`: the duplicated value may already be part of an intentional previous override.

When summarising, say which previous plugin it matches if the override chain readback exposes that participant.
