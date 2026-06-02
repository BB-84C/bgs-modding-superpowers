---
id: archive-precedence.fo4-next-gen-ba2-version-bump.v1
title: Fallout 4 next-gen updates can break older BA2 tooling assumptions
domains: [archive-precedence, version-differences, debugging]
appliesTo:
  games: [Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
canonical:
  answer: Fallout 4 next-gen era updates changed BA2/archive compatibility assumptions, so archive tooling and packed-asset failures must be checked against the runtime version.
  confidence: medium
queryKeys: [Fallout 4 next-gen BA2, BA2 version, archive breakage, next gen update]
severity: high
sources:
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: "Appendix: BGS modding source list"
  - kind: community-forum
    url: "https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/"
    ref: AFK Mods UFO4P forum
variants:
  Fallout4VR:
    warnings:
      - code: VR_RUNTIME_DIVERGENCE
        severity: high
        text: Fallout 4 VR does not track the flat game's next-gen runtime one-to-one; verify archive compatibility against the actual VR executable and toolchain.
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 next-gen updates can break older BA2 tooling assumptions

Do not assume every BA2 packed by older Fallout 4 tooling remains compatible with every next-gen runtime scenario.
When a packed asset disappears or an archive fails to load after an update, check archive version/tool compatibility before changing plugin order.

For modpack work, record which FO4 runtime branch the archive was built for.
This is especially important when supporting both flat Fallout 4 and Fallout 4 VR.
