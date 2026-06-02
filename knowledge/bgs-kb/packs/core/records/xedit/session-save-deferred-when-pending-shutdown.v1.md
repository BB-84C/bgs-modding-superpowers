---
id: xedit.session-save-deferred-when-pending-shutdown.v1
title: session.save with savedFilesPendingShutdown > 0 is deferred, not durable
kind: rule-candidate
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A session.save response that reports savedFilesPendingShutdown is not durability proof; prove persistence by saving, restarting the daemon with a new PID, and reading the changed state back.
  confidence: verified-project-doc
queryKeys: [session.save, savedFilesPendingShutdown, durability, save restart readback]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Save & durability semantics
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: Implications for later batches
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# session.save with savedFilesPendingShutdown > 0 is deferred, not durable

`session.save` can report files that are pending shutdown rather than written immediately.
That response is a useful support signal, but it is not proof the plugin on disk has the intended state.

For mutating workflows, the acceptance loop is save, stop or restart the daemon, confirm the PID changed, then read back the affected record, header, or master list.
Only the post-restart readback proves durability.

Agents should treat a pending-shutdown save as a required follow-up step, not as a green completion state.
