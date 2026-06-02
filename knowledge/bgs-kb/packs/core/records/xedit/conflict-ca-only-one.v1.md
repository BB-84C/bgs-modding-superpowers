---
id: xedit.conflict-ca-only-one.v1
title: caOnlyOne means no override chain exists for that record
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: caOnlyOne means xEdit sees only one participant for the record, so an MCP conflict audit should report no conflict while still allowing reference and winner readback.
  confidence: verified-project-doc
queryKeys: [caOnlyOne, one participant, no conflict, single record]
severity: low
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

# caOnlyOne means no override chain exists for that record

Map `caOnlyOne` to `no_conflict` in the MCP verdict layer.
It says there is no competing override for that FormID in the loaded files.

This does not prove the record is safe in every gameplay sense.
It only answers the override-chain question.

For deletion or mark-deleted workflows, still call `records.referenced_by` before changing anything.
