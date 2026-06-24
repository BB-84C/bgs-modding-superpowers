---
id: starfield-localization.protected-spans.v1
title: Starfield localization must preserve IDs, placeholders, and export structure
kind: rule
domains: [plugin-format]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Translate Starfield user-facing text, but preserve export identifiers, filenames, placeholders, generated tokens, and delivery-folder structure so the Creation Kit can compile and delocalize the content safely.
  confidence: high
queryKeys: [Starfield localization, protected spans, TextExport, TagifyPlugin, CompileTextExport]
severity: high
sources:
  - kind: project-internal-doc
    ref: .artifacts/starfield wiki html/Creation Localization Process - XWiki.html
    sectionPath: Tagify, ExportText, CompileTextExport, DelocalizeMasterfile
  - kind: project-internal-doc
    ref: .artifacts/starfield wiki html/Localized Descriptions.html
    sectionPath: Bethesda.net localized descriptions
  - kind: official
    url: "https://store.steampowered.com/app/2722710/"
    ref: Starfield Creation Kit Steam page
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield localization must preserve IDs, placeholders, and export structure

Starfield's Creation Kit localization path is export-and-compile based. The safe rule is to translate only the human-facing string column or file text, while preserving every structural span that lets the CK map the translation back to records.

Protected spans include plugin filenames, unique book/message filenames, TextExport row identifiers, voice type / alias / speaker columns used as context, FormID-derived or EditorID-derived labels, Papyrus property names, empty strings, percent placeholders, bracketed variables, and any generated token whose value is resolved by game data rather than written prose. Dialogue export files are useful translation aids, but they are not deliverables; completed dialogue translations must be mapped back into the relevant TextExport rows.

The folder shape is also protected. A localized delivery mirrors the exported source: plugin folder, language-code folder, Books, Messages, and TextExport.txt. Renaming files or flattening folders can make a good translation impossible to compile. Bethesda.net descriptions are separate metadata: Starfield uploads can select a default description and localized alternatives based on the viewer's Bethesda.net language setting.

If CAT tooling or an LLM modifies identifiers, stop and restore from the English export before compiling. A successful localization pass is structurally identical to the source export except for translated user-visible text.

> Source note: portions paraphrased from a community-archived Bethesda Creation Kit
> wiki snapshot (circa 2025-05-14). The information surfaced here represents
> community reverse-engineering of behavior visible in the live Creation Kit, not
> Bethesda's official documentation.
