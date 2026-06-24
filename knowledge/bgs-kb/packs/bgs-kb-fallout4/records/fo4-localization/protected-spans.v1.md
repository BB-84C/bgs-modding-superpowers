---
id: fo4-localization.protected-spans.v1
title: Fallout 4 localization must protect engine tokens and generated spans
kind: rule
domains: [plugin-format, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 translators should translate player-facing prose while preserving EditorID-derived terms, placeholders, control codes, and generated strings whose meaning is assembled by engine or Papyrus state.
  confidence: high
queryKeys: [Fallout 4 localization, xTranslator, protected spans, placeholders, EditorID]
severity: high
sources:
  - kind: wiki
    url: "https://falloutck.uesp.net/wiki/Category:Papyrus"
    ref: UESP Fallout 4 Papyrus reference
  - kind: tooling-docs
    url: "https://www.nexusmods.com/fallout4/mods/134"
    ref: xTranslator Fallout 4 Nexus page
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 4 localization must protect engine tokens and generated spans

Fallout 4 localization is record work, not free-form prose editing. Translate player-visible names, messages, books, dialogue, and UI text, but protect spans that the engine, Papyrus, or tooling expects to remain structurally intact. Empty strings, `%` placeholders, bracketed control codes, script variables, FormID-derived labels, and INI-like tokens should survive translation unless a tool-specific rule proves otherwise.

Watch for generated display strings. Names such as ownership labels, item variants, legendary modifiers, and workshop strings may be assembled from multiple records or runtime state; translating one piece as a natural sentence can break composition in another context. EditorIDs and script property names are not prose. Papyrus-exposed text can be user-facing, but the variable name, property link, and token syntax around it are protected.

The safe workflow is to use xTranslator-style rule sets, preserve protected spans first, then review the rendered in-game context. FO4VR inherits the same plugin-string risks but may expose text through different VR UI widgets, so do not assume flat-screen layout length is safe. Vault-Tec is not responsible for mojibake, broken `%s` tokens, or existential dread caused by translating a FormID.

When in doubt, leave the token untouched and add a reviewer note rather than guessing.
