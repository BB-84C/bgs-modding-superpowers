---
id: fo4-conflicts.leveled-list-and-npc-overhaul-patterns.v1
title: Fallout 4 leveled-list and NPC overhaul conflicts need semantic review
kind: rule
domains: [file-conflicts, xedit, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Automated list merging can reduce structural Fallout 4 conflicts, but leveled-list distribution and NPC overhaul coherence still require human xEdit review and a curator patch.
  confidence: high
queryKeys: [Fallout 4 leveled list, NPC overhaul, Bashed Patch, Complex Sorter, xEdit]
severity: critical
sources:
  - kind: tooling-docs
    url: "https://wrye-bash.github.io/docs/Wrye%20Bash%20General%20Readme.html"
    ref: Wrye Bash documentation
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: xEdit documentation
  - kind: project-internal-doc
    ref: BB84 corpus Q16 verbatim and WL2 recon, Complex Sorter INNR series
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 4 leveled-list and NPC overhaul conflicts need semantic review

## Perspective: OBJECTIVE

Fallout 4 leveled-list conflicts are silent failure modes. A bad merge usually does not crash; it makes items stop appearing, creates absurd spawn rates, or equips NPCs with incoherent outfits. Wrye Bash-style automation can merge some structural list edits, but it does not know the intended economy, faction identity, or encounter pacing of the pack. NPC overhauls add another conflict axis: face data, tint layers, race, voice, template inheritance, outfit records, and headpart assets can be split across plugins and loose files.

The safe pattern is to inspect all LL and NPC winners in xEdit, let automated tools generate draft structure where useful, then author a final curator patch for semantic intent. The patch answers a design question: what should this faction, level band, vendor, or named NPC actually become?

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84 treats heavy LL overhauls as "must custom patch + human review" work. WL2's Complex Sorter and 4estGimp INNR-style rules show this discipline: item classification and distribution are maintained as pack logic, not delegated completely to automation. This is one curator's reference pattern, not a universal style requirement.
