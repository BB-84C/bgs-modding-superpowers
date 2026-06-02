---
id: archive-precedence.ini-archive-list-per-game.v1
title: INI archive lists can influence archive loading before conflict diagnosis
domains: [archive-precedence, file-conflicts, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
  engineFamilies: [gamebryo, creation-engine]
canonical:
  answer: Archive load behavior can depend on game INI archive-list settings such as `SArchiveList`, so missing archived assets require INI inspection as well as MO2 and plugin-order checks.
  confidence: high
queryKeys: [SArchiveList, archive list, Skyrim.ini, Fallout.ini, Fallout4.ini, INI archive load]
severity: high
sources:
  - kind: wiki
    url: "https://stepmodifications.org/wiki/Main_Page"
    ref: STEP Wiki
  - kind: tooling-docs
    url: "https://github.com/ModOrganizer2/modorganizer/wiki"
    ref: Mod Organizer 2 wiki
related: [archive-precedence.bsa-vs-ba2-by-game.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# INI archive lists can influence archive loading before conflict diagnosis

Some Bethesda runtimes consult INI archive-list settings, historically including keys such as `SArchiveList`, to decide which archives are loaded.
The relevant INI path is game-specific and can be virtualized or profile-specific under MO2.

If an archived asset appears missing, inspect the profile INI layer before assuming the plugin is sorted incorrectly.
This record is separate from loose-file precedence: it is about whether an archive participates in the runtime view at all.
