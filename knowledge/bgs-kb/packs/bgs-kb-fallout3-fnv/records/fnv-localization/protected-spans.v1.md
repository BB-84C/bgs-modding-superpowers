---
id: fnv-localization.protected-spans.v1
title: Protected spans for Fallout 3 and New Vegas localization
kind: rule
domains: [plugin-format, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: In Fallout 3 and New Vegas localization, translate player-visible prose but preserve placeholders, control tokens, script-sensitive identifiers, and generated-name structures that the engine or scripts expect.
  confidence: high
queryKeys: [FNV localization protected spans, FO3 localization placeholders, xTranslator New Vegas, protected tokens]
severity: high
sources:
  - kind: wiki
    ref: UESP Fallout New Vegas reference
    url: https://en.uesp.net/wiki/Fallout:New_Vegas
    sectionPath: Game data and interface terminology
  - kind: tooling-docs
    ref: xTranslator New Vegas support
    url: https://www.nexusmods.com/newvegas/mods/66810
    sectionPath: Supported games and translation workflow
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Protected spans for Fallout 3 and New Vegas localization

Fallout 3 and New Vegas localization should change player-facing meaning, not engine contracts. Dialogue, terminal prose, item names, perk descriptions, and quest objectives are normal translation targets. Protected spans include formatting placeholders, percent-style variables, bracketed control text, empty strings used as sentinels, script-sensitive tokens, and any substring whose value is generated from a FormID or EditorID relationship rather than authored prose.

Be careful with names derived from object ownership or templating, such as possessive generated forms, faction/rank labels, or dynamically assembled item names. If a script, menu XML, or NVSE/JIP function expects an exact token, translating it can break behavior even though the string looks visible. EditorIDs themselves are not display text. A display string that merely resembles an EditorID should be inspected before translation, not guessed from capitalization.

For FO3/FNV-era plugins, localization is often stored directly in plugin records rather than in the later Creation Engine string-file workflow. That makes xTranslator-style dictionary discipline important: protect tokens first, translate repeated terms consistently, then review in-game where the text appears. TTW adds another hazard: Fallout 3 terms may appear inside the New Vegas runtime and must stay coherent with both Capital Wasteland and Mojave terminology. Mixed-language UI is a usability failure, but broken tokens are worse; when uncertain, preserve the token and add a translator note.
