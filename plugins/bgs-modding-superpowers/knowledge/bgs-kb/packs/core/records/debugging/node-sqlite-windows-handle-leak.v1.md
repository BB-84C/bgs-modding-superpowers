---
id: debugging.node-sqlite-windows-handle-leak.v1
title: node:sqlite can leave Windows kb.sqlite handles busy after parallel CLI runs
kind: gotcha
domains: [debugging, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: On Windows, repeated or parallel bgs-kb CLI invocations can leave node:sqlite file handles busy long enough that rebuilding a pack fails with EBUSY on kb.sqlite; wait, use a fresh shell, clear stale Node workers, or change the build path to temp-file plus atomic move.
  confidence: verified-project-doc
queryKeys: [node:sqlite, Windows EBUSY, kb.sqlite locked, parallel build, stale Node handle, rebuild pack]
severity: high
sources:
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-02 - KB-4 closeout / Now known
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# node:sqlite can leave Windows kb.sqlite handles busy after parallel CLI runs

During KB-4, many subagent workers invoked the BGS KB CLI in parallel on Windows.
After that fan-out, the core pack's `kb.sqlite` could not be unlinked by the orchestrator process even after retries, producing `EBUSY` on rebuild while the record files themselves were valid.

Treat this as a local build-artifact handle issue, not a record-authoring failure.
Recovery options are: wait and retry, run the rebuild in a fresh shell/session, terminate stale Node workers if the user permits process cleanup, or improve the builder to write a temporary SQLite file and atomically move it into place after all handles close.

Do not weaken KB record validation because of this symptom.
Validate the record tree first, then rebuild when the file handle is no longer held.
