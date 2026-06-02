---
id: plugin-format.plugin-type-esm-esp-esl-matrix.v1
title: ESM, ESP, and ESL carry different load and capacity semantics
domains: [plugin-format, xedit]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "ESM, ESP, and ESL are not just filename preferences: master flags, light-master flags, extension, load position, and FormID capacity all affect how the engine and tools treat a plugin."
  confidence: verified-tooling
variants:
  SkyrimSE:
    additions:
      - Skyrim SE introduced ESL support after the original Skyrim LE era; verify the target runtime before applying light-plugin advice.
  Starfield:
    additions:
      - Treat Starfield plugin-type guidance as Creation Engine 2-specific and verify with current xEdit/Mutagen support before assuming Skyrim or Fallout 4 limits transfer unchanged.
queryKeys: [ESM, ESP, ESL, light master, plugin type matrix, master flag]
severity: high
sources:
  - kind: wiki
    ref: UESP Skyrim Mod File Format
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format
    sectionPath: Mod Plugin Types
  - kind: tooling-docs
    ref: Mutagen Docs — Compaction
    url: https://mutagen-modding.github.io/Mutagen/plugins/Compaction/
    sectionPath: Setting Small Master Flag
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ESM, ESP, and ESL carry different load and capacity semantics

An `.esm` extension or ESM header flag marks a file as master-like; an `.esp` is the usual plugin extension; an `.esl` or light-flagged plugin enters the light-master model.
Modern tooling also distinguishes file extension from header flags: a flagged ESP can behave as a light master without using the `.esl` extension.

Use the matrix as a decision aid, not as a blind conversion recipe.
Changing type or flags can alter load behavior, FormID validity, and compatibility with dependent plugins.

Verify the target game and runtime before applying light-master advice.
