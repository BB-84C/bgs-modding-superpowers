---
id: pack-curation.numerical-mainframe-pattern.v1
title: Choose a numerical mainframe for overlapping economy and reward systems
kind: workflow
domains: [install-planning, engine]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: When multiple mods edit economy, bounty, wage, reward, or price values, pick one numerical mainframe and patch the other systems into that scale instead of letting plugin order arbitrarily choose the winner.
  confidence: verified-project-doc
queryKeys: [numerical mainframe, economy framework, value patching, bounty reward, wage tick]
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 Lane 3 audit synthesis
    sectionPath: numerical compatibility design
related: [mod-evaluation.systemic-design-fit.v1]
lastReviewed: "2026-06-29"
schemaVersion: 1
---

# Choose a numerical mainframe for overlapping economy and reward systems

Economy and reward mods often encode an internal scale: vendor credits, bounty rewards, wage ticks, item prices, upkeep costs, or related globals. If several mods edit the same family of values, raw plugin priority produces an accidental economy.

Pick one mainframe mod whose numerical design should define the pack's baseline. Then patch other mods to preserve their relative intent inside that baseline instead of accepting whichever override wins.

Do not stop at GLOB records when scripts also write or read values. Some mods store reward arrays, VMAD data, quest script properties, or runtime recalculation paths that can overwrite or reinterpret a patched record value.

Reference case: a Space Economy-style mainframe can define the baseline while Ronin-style bounty globals and Starvival-style wage or survival costs are patched to remain coherent inside that scale.
