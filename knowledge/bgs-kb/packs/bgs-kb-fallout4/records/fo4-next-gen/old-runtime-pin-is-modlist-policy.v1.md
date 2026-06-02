---
id: fo4-next-gen.old-runtime-pin-is-modlist-policy.v1
title: Staying on an old Fallout 4 runtime is a modlist policy decision
domains: [version-differences, install-planning]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Pinning or downgrading Fallout 4 to preserve pre-next-gen compatibility is a modlist-level policy that must be documented, not an invisible troubleshooting trick.
  confidence: verified-official
queryKeys: [downgrade Fallout 4, old runtime, Steam beta, pre next-gen modlist]
severity: high
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Staying on an old Fallout 4 runtime is a modlist policy decision

Some Fallout 4 lists intentionally target an older runtime because their native plugin stack is built there.
That can be valid, but it must be explicit.

Document the expected executable version, F4SE build, and update-prevention instructions.
Otherwise users will silently drift onto a branch the list was not tested against.
