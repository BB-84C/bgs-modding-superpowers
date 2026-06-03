---
id: xedit.request-args-object.v1
title: xEdit daemon request args are always objects
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The xEdit automation request envelope always carries args as an object; callers should not send scalar or positional argument payloads.
  confidence: verified-project-doc
queryKeys: [args object, request args, invalid_request, xedit_call]
severity: medium
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Daemon protocol essentials
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit daemon request args are always objects

Every native daemon command receives an object under `args`, even when the command takes no parameters.
The empty-argument form is `{}` rather than null, an array, or a string.

This matters for `xedit_call`, where agents may be tempted to pass a quick scalar payload.
Use schema validation to normalize or reject the request before it reaches the daemon.

If the daemon answers `invalid_request`, inspect the request envelope before debugging the target record.
