---
id: ttw-interop.ttw-fo3-mod-compatibility-needs-conversion.v1
title: Fallout 3 mods are not automatically TTW-compatible
domains: [install-planning, file-conflicts, version-differences]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: TTW compatibility depends on what the Fallout 3 mod edits; textures are often safer, but meshes, scripts, shared records, and deleted/reused content may need TTW-specific conversion or patches.
  confidence: medium
queryKeys: [TTW FO3 mods, FO3 mod conversion, TTW patches, mesh replacement, texture mods]
severity: high
sources:
  - kind: community-forum
    ref: The Best of Times FAQ
    url: https://thebestoftimes.moddinglinked.com/faq.html
    sectionPath: Mod compatibility
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 3 mods are not automatically TTW-compatible

TTW changes the runtime and many records that FO3 mods expect.
The FAQ distinguishes relatively safe asset-only cases from mods that edit shared records, scripts, meshes, or content that TTW has already cleaned and fixed.

Do not assume a raw FO3 plugin can simply be enabled in a TTW New Vegas profile.
Look for a TTW patch or conversion guidance, then verify in xEdit.
