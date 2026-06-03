---
id: xedit.jobs-dry-run-default.v1
title: xEdit jobs default to dry-run unless apply mode explicitly sets dryRun false
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: xEdit async jobs are bounded to one active job, and apply-mode jobs remain non-mutating unless the caller explicitly passes dryRun false.
  confidence: verified-project-doc
queryKeys: [jobs.start, dryRun, async job, apply mode, single active job]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: jobs.* commands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit jobs default to dry-run unless apply mode explicitly sets dryRun false

The job surface is built for long-running operations and has a single-active-job constraint.
For apply-capable jobs, omitting `dryRun` keeps the operation non-mutating.

Agents should surface that default in plans and only set `dryRun: false` after the user has accepted the mutation path.
Polling should go through job lifecycle calls, not repeated start attempts.

This record helps distinguish safe analysis jobs from explicit apply operations.
