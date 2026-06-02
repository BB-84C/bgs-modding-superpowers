---
id: fo4-next-gen.april-2024-update-created-runtime-split.v1
title: The Fallout 4 next-gen update created a practical runtime split for modlists
domains: [version-differences, install-planning]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 modlists must distinguish pre-next-gen and next-gen runtime branches because native plugins, F4SE builds, archives, and Creations-era content may not be interchangeable.
  confidence: verified-official
queryKeys: [Fallout 4 next-gen, 1.10.984, 1.11.221, runtime split, April 2024]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: "Appendix: BGS modding source list"
related: [archive-precedence.fo4-next-gen-ba2-version-bump.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# The Fallout 4 next-gen update created a practical runtime split for modlists

The next-gen update did not just add content; it changed the runtime branch that native tooling targets.
F4SE's public compatibility matrix exposes separate builds for different Fallout 4 versions.

Modlist documentation should state which runtime it targets.
Without that pin, users can install a working-looking list whose DLLs and packed assets belong to another branch.
