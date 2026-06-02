---
id: xedit.system-describe-game-name.v1
title: system.describe reports the friendly game label in gameName
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: system.describe returns the user-facing game label under gameName, while gameMode may carry an internal token such as gmFO4.
  confidence: verified-project-doc
queryKeys: [system.describe, gameName, gameMode, gmFO4]
severity: medium
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# system.describe reports the friendly game label in gameName

`system.describe` separates the friendly game label from the internal game-mode token.
Batch 1 learned that `gameName` is the better user-facing value, while `gameMode` may look like `gmFO4`.

Session summaries and human-facing readbacks should prefer `gameName` when it exists.
Keep `gameMode` available for low-level diagnostics and daemon compatibility checks.

If a tool reports a surprising game mode, compare both fields before assuming the wrong game launched.
