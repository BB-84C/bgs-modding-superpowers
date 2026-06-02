---
id: ttw-interop.mo2-mod-folder-is-ttw-installer-output.v1
title: TTW installer output should land as an MO2 mod folder
domains: [install-planning, file-conflicts]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: The Best of Times directs the TTW installer output into an MO2 mods folder named Tale of Two Wastelands, then enables that mod in MO2 to populate the plugin pane.
  confidence: high
queryKeys: [TTW MO2 folder, Tale of Two Wastelands mod folder, installer output, MO2 left pane]
severity: critical
sources:
  - kind: community-forum
    ref: The Best of Times TTW install page
    url: https://thebestoftimes.moddinglinked.com/ttw.html
    sectionPath: Installing Tale of Two Wastelands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# TTW installer output should land as an MO2 mod folder

The TTW install flow is overlay-oriented: create the MO2 mod folder, point the installer output there, and enable the resulting mod in MO2.
Files landing one directory too high or too low produce a missing or greyed-out mod rather than a valid TTW stack.

For this repo's operating rules, this is also the safe pattern: do not copy TTW payload directly into a live game Data folder.
