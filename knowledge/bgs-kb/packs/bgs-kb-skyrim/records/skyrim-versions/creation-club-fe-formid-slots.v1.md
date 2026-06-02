---
id: skyrim-versions.creation-club-fe-formid-slots.v1
title: Skyrim Creation Club ESL FormIDs use install-specific FE slots
domains: [plugin-format, load-order, version-differences]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "UESP documents Skyrim Creation Club ESL FormIDs as FE xxx YYY, where the middle slot is assigned from the installed Creation order and can vary between users."
  confidence: high
queryKeys: [FE FormID, Creation Club, ESL slot, FExxx, Skyrim FormID]
severity: high
sources:
  - kind: wiki
    ref: UESP Skyrim Form ID
    url: https://en.uesp.net/wiki/Skyrim:Form_ID
    sectionPath: Creation Club
related: [plugin-format.light-plugin-formid-range.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim Creation Club ESL FormIDs use install-specific FE slots

Do not hardcode `FExxx` Creation Club slots across users.
UESP shows the `FE xxx YYY` layout and explains that the slot depends on installed Creation order.

Use xEdit, the console, or runtime lookup to resolve the actual FormID in the user's load order.
The final local digits are more portable than the middle slot.

This is a Skyrim-specific variant of the broader light-plugin FormID warning.
