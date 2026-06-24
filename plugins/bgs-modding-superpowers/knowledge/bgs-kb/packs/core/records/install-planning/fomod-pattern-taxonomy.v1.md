---
id: install-planning.fomod-pattern-taxonomy.v1
title: FOMOD installer pattern taxonomy for modpack curators
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "A FOMOD is a ModuleConfig.xml decision tree: classify whether it is non-interactive, mutually exclusive, additive, or flag-conditioned before choosing options or automating installation."
  confidence: high
queryKeys: [FOMOD, ModuleConfig.xml, installer choices, condition flags, SelectExactlyOne, mod installer]
severity: high
sources:
  - kind: tooling-docs
    url: "https://github.com/GandaG/fomod-schema"
    ref: "FOMOD schema project"
  - kind: community-forum
    url: "https://wiki.nexusmods.com/index.php/FOMod_XML_schemas"
    ref: "Nexus Mods Wiki FOMod XML schemas"
  - kind: community-forum
    url: "https://wiki.nexusmods.com/index.php/How_to_create_mod_installers"
    ref: "Nexus Mods Wiki installer authoring guide"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# FOMOD installer pattern taxonomy for modpack curators

FOMOD installers are not magic UI; they are a `ModuleConfig.xml` decision tree that maps user choices, flags, dependency tests, and file instructions into the final installed file set. Curators should classify the pattern before clicking through or attempting non-interactive automation.

Pattern A is the non-interactive or nearly non-interactive installer: one fixed file layout, maybe with documentation pages, and no meaningful choice. It can be automated safely if the source/destination file mapping is clear. Interactive installers require a stricter read. Group types matter: `SelectExactlyOne` means a variant decision, `SelectAtMostOne` means optional mutually-exclusive content, `SelectAtLeastOne` means a required additive set, `SelectAny` means independent toggles, and `SelectAll` is an author-forced group.

This classification should be captured in the install note before the archive enters a long-lived profile.

Flags and conditions are the usual containment breach. A page may set a condition flag, a later page may test it, and files may install only when dependency expressions match. Dependency checks can target game version, installed plugins, or earlier selections, so curators must preserve the chosen path in notes. Source-file instructions also matter: priority, destination path, and folder-vs-file rules decide what loose files will exist after the installer finishes.

Common anti-patterns are mutually-exclusive variants exposed as independent toggles, condition flags whose names do not match their behavior, and compatibility patches hidden behind late pages without explaining the parent mod relationship. Vortex 0.5+ unified-path handling also means old fomod assumptions about manager-specific path roots should be checked against the current schema rather than guessed.
