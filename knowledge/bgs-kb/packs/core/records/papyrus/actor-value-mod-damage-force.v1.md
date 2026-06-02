---
id: papyrus.actor-value-mod-damage-force.v1
title: ModActorValue, DamageActorValue, and ForceActorValue affect actor values differently
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: "Actor value functions are not interchangeable: ModActorValue changes the current maximum-style value, DamageActorValue damages current value, and ForceActorValue sets a forced current value through modifiers."
  confidence: verified-tooling
queryKeys: [ModActorValue, DamageActorValue, ForceActorValue, actor value, AV side effects]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki ModActorValue - Actor
    url: https://ck.uesp.net/wiki/ModActorValue_-_Actor
    sectionPath: Notes
  - kind: wiki
    ref: Creation Kit Wiki DamageActorValue - Actor
    url: https://ck.uesp.net/wiki/DamageActorValue_-_Actor
    sectionPath: Notes
  - kind: wiki
    ref: Creation Kit Wiki ForceActorValue - Actor
    url: https://ck.uesp.net/wiki/ForceActorValue_-_Actor
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ModActorValue, DamageActorValue, and ForceActorValue affect actor values differently

Choose the actor-value function by intended side effect.
`DamageActorValue` damages the current value; negative amounts are treated as positive on the CK page.

`ModActorValue` is documented as distinct because it changes the maximum-style/current total rather than just applying damage.
`ForceActorValue` forces the value through a permanent-modifier-style path, while base value changes belong elsewhere.

Do not swap these calls during patching without testing health/magicka/stamina readback in-game.
