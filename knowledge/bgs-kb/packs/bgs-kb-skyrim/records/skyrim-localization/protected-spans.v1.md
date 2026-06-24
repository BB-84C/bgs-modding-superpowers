---
id: skyrim-localization.protected-spans.v1
title: Skyrim localization protected spans
kind: rule
domains: [plugin-format, papyrus, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [gamebryo, creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "When localizing Skyrim records, translate player-facing prose but preserve engine tokens, placeholders, EditorID-derived identifiers, and strings whose value is generated or consumed by scripts."
  confidence: high
queryKeys: [Skyrim localization, protected spans, EditorID, Papyrus strings, xTranslator, placeholders]
severity: high
sources:
  - kind: official
    url: "https://ck.uesp.net/wiki/Localization"
    ref: "Creation Kit Wiki localization"
  - kind: official
    url: "https://ck.uesp.net/wiki/Editor_ID"
    ref: "Creation Kit Wiki Editor ID"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/134"
    ref: "xTranslator Nexus page"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Skyrim localization protected spans

Skyrim localization is not a free-text rewrite pass. Translate `FULL`, `DESC`, dialogue, books, messages, and other player-facing text, but protect spans the engine or tooling treats as identifiers. EditorIDs are not display prose. Generated names derived from forms, owners, enchantments, or templated records can depend on FormIDs and record structure; changing their token shape may break consistency even when the string looks natural in isolation.

Protect empty strings, `%` placeholders, bracketed or brace-style tokens used by scripts/UI, menu control glyphs, color or formatting escapes, and any text that a Papyrus script compares literally. Also protect property names, animation-event names, quest aliases, package conditions, file paths, sound markers, and MCM/internal keys unless the mod author documents that they are user-facing. If a string appears both in a record and in a script property or JSON/MCM config, treat it as a contract until proven otherwise.

xTranslator-style workflows help by classifying known fields and carrying translation memory, but the curator still owns context. For ambiguous strings, inspect the record type, references, and whether the text appears in scripts or configuration. The safe rule is: translate what the player reads; preserve what the engine, Papyrus, UI framework, or patching tool must recognize.

Name generation is especially risky in Skyrim because articles, ownership, enchantment labels, and object names can be assembled from multiple fields. If the localized result must preserve grammatical order, patch the visible record text deliberately instead of editing hidden identifiers to make a sentence look better.
