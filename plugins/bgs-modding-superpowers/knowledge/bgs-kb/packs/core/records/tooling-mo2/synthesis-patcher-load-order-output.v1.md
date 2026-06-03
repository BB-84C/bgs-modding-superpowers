---
id: tooling-mo2.synthesis-patcher-load-order-output.v1
title: Synthesis patchers generate an output plugin from the current load order
domains: [tooling.mutagen, install-planning, load-order]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
  engineFamilies: [gamebryo, creation-engine]
  excludes: [Starfield]
canonical:
  answer: Synthesis runs Mutagen-based patchers over the selected load order and emits an output patch plugin, so the patch should be regenerated after load-order or modlist changes.
  confidence: verified-tooling
queryKeys: [Synthesis, patcher, Synthesis.esp, Mutagen patcher, regenerate patch]
severity: high
sources:
  - kind: tooling-docs
    url: "https://mutagen-modding.github.io/Synthesis/"
    ref: Synthesis documentation
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Synthesis patchers generate an output plugin from the current load order

Synthesis patchers are code-driven transformations over a load order.
The documented pipeline can combine multiple patchers into an output plugin such as `Synthesis.esp`.

Because the output depends on the input load order, adding, removing, or moving mods can stale the patch.
Regenerate and re-check conflicts after changing the list that a Synthesis patcher consumes.
