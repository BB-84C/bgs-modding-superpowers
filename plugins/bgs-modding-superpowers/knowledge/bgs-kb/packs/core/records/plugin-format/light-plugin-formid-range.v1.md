---
id: plugin-format.light-plugin-formid-range.v1
title: Light plugins require compact FormIDs in the light range
domains: [plugin-format, xedit]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: Light-master conversion requires records to fit the light-plugin FormID range; compaction can renumber records, so references and persistence must be verified after the change.
  confidence: verified-tooling
variants:
  SkyrimSE:
    additions:
      - UESP documents Skyrim SE ESL behavior and notes expanded light-plugin capacity in modern runtimes; older SSE runtimes need version-aware caution.
  Fallout4:
    additions:
      - Fallout 4 light-plugin workflows use the same xEdit/MCP ESL analysis and apply path, but verify against the active FO4 runtime before converting production plugins.
  Starfield:
    additions:
      - Starfield is Creation Engine 2; treat light/medium/full master style support as tooling-version-sensitive and check current capabilities before applying older game assumptions.
queryKeys: [ESL FormID range, light plugin, compact FormIDs, CompactToSmallMaster, plugin.esl.analyze]
severity: critical
sources:
  - kind: tooling-docs
    ref: Mutagen Docs — Compaction
    url: https://mutagen-modding.github.io/Mutagen/plugins/Compaction/
    sectionPath: Compaction; Compatibility Detection
  - kind: wiki
    ref: UESP Skyrim Mod File Format
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format
    sectionPath: Mod Plugin Types
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Glossary
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Light plugins require compact FormIDs in the light range

Light plugins buy load-order capacity by constraining FormIDs.
Mutagen's compaction docs describe Small/Light compaction as a range-limited operation that may reassign out-of-range records.

That renumbering is the dangerous part: references must still resolve after compaction, save, restart, and readback.
Use `plugin.esl.analyze` before `plugin.esl.apply`, and do not set the flag by hand just because the extension says `.esp` or `.esl`.

Game-specific runtime limits vary enough that the active game and tool capabilities must be checked before conversion.
