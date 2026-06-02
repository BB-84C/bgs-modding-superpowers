---
id: fo4-tooling.bodyslide-outfit-studio-fo4-assets.v1
title: BodySlide and Outfit Studio cover Fallout 4 body and outfit asset workflows
domains: [install-planning, file-conflicts]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: BodySlide and Outfit Studio support Fallout-family body and outfit conversion workflows, so generated meshes should be treated as asset outputs that can override installed mod files.
  confidence: verified-tooling
queryKeys: [BodySlide, Outfit Studio, Fallout 4 bodies, CBBE, generated meshes]
severity: high
sources:
  - kind: tooling-docs
    url: "https://github.com/ousnius/BodySlide-and-Outfit-Studio"
    ref: BodySlide and Outfit Studio GitHub
related: [archive-precedence.mo2-overwrite-generated-assets.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# BodySlide and Outfit Studio cover Fallout 4 body and outfit asset workflows

BodySlide and Outfit Studio are asset-generation tools, not plugin sorters.
Their outputs are meshes and related files that participate in normal file conflict resolution.

When a body or outfit looks wrong in FO4, check generated output location and asset winners before changing ESP order.
Move durable generated files out of Overwrite into a named mod for reviewable modlist state.
