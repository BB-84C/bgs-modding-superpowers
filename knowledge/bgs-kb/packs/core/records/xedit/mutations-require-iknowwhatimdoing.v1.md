---
id: xedit.mutations-require-iknowwhatimdoing.v1
title: xEdit mutating commands require the daemon to launch with IKnowWhatImDoing
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Mutating xEdit commands are gated by the daemon's IKnowWhatImDoing launch state; read-only commands may work while write commands correctly refuse.
  confidence: verified-project-doc
queryKeys: [IKnowWhatImDoing, consent_required, mutating commands, write gate]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Mutation policy
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit mutating commands require the daemon to launch with IKnowWhatImDoing

The write gate is intentional.
Creating records, editing elements, changing file headers, and saving files require a daemon launch mode that acknowledges mutating risk.

Agents should treat `consent_required` as a safety refusal, not a transient daemon error.
The recovery is to stop and obtain the right consent and launch shape, not to bypass the MCP.

Read-only success does not prove the daemon is allowed to mutate.
