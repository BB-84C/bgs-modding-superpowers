---
id: xedit.dynamic-record-signature-capabilities.v1
title: records.create signature support is dynamic and comes from system.capabilities
domains: [xedit, plugin-format]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The xEdit fork no longer relies on a fixed KYWD/MISC creation whitelist; record-creation support should be read from system.capabilities for the active daemon.
  confidence: verified-project-doc
queryKeys: [records.create, signature support, system.capabilities, KYWD, MISC]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Mutation policy
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# records.create signature support is dynamic and comes from system.capabilities

Record-creation support depends on what the active daemon advertises.
The old static whitelist model is not the contract for the forked automation surface.

Before creating records, read the capability digest or live capabilities and check whether the desired signature is supported.
This avoids both false refusals and unsafe assumptions about unsupported signatures.

For read-only KB guidance, treat signature support as daemon-reported state, not a hard-coded table.
