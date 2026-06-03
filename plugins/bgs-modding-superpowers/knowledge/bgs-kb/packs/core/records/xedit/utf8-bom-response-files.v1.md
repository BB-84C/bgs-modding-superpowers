---
id: xedit.utf8-bom-response-files.v1
title: xEdit daemon writes response files as UTF-8 with BOM on Windows
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: On Windows, xEdit automation response files may begin with a UTF-8 BOM, so adapters must strip leading 0xFEFF before passing the text to JSON.parse.
  confidence: verified-project-doc
queryKeys: [UTF-8 BOM, "0xFEFF", JSON.parse, response file]
severity: high
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit daemon writes response files as UTF-8 with BOM on Windows

The Windows response-file path can produce JSON text with a leading UTF-8 BOM.
JavaScript's `JSON.parse` does not accept that marker as part of the JSON document.

Adapters should strip a leading `0xFEFF` before parsing and treat that as normal daemon I/O hygiene, not corrupt output.
Do this at the transport boundary so domain tools receive already-parsed envelopes.

If a response file looks valid in an editor but parsing fails at byte zero, check for the BOM first.
