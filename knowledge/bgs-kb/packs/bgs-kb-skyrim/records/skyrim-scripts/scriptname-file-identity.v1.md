---
id: skyrim-scripts.scriptname-file-identity.v1
title: Skyrim Papyrus ScriptName is the script identity, not a mod-local namespace
domains: [papyrus, file-conflicts, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "A Papyrus source file starts with a ScriptName header, so two mods shipping the same script name are competing over one global compiled script identity."
  confidence: verified-tooling
queryKeys: [ScriptName, psc, pex, script conflict, loose script overwrite]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki Script File Structure
    url: https://ck.uesp.net/wiki/Script_File_Structure
    sectionPath: Header Line
related: [archive-precedence.loose-over-archive.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim Papyrus ScriptName is the script identity, not a mod-local namespace

The first non-comment line of a Papyrus script declares `ScriptName`.
That name is the compiled script identity used by the game.

Skyrim does not give each ESP its own private script namespace.
If two mods ship different `SomeScript.pex` files with the same ScriptName, asset precedence decides which compiled script wins.

When diagnosing a script conflict, inspect loose files and BSA script assets as well as plugin records.
