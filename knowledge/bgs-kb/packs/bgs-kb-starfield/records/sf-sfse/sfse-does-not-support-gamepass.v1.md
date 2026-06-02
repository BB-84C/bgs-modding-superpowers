---
id: sf-sfse.sfse-does-not-support-gamepass.v1
title: SFSE does not support the Windows Store or Game Pass Starfield release
domains: [version-differences, install-planning, debugging]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: The SFSE home page says it does not support the Windows Store/Game Pass Starfield release, so SFSE-dependent modlists should require the supported Steam runtime.
  confidence: verified-official
queryKeys: [SFSE Game Pass, Windows Store Starfield, unsupported storefront]
severity: critical
sources:
  - kind: official
    url: "https://sfse.silverlock.org/"
    ref: Starfield Script Extender home
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SFSE does not support the Windows Store or Game Pass Starfield release

SFSE explicitly excludes the Windows Store/Game Pass release.
That means a user on that storefront cannot satisfy an SFSE-dependent modlist by changing plugin order.

Modlist requirements should state the storefront requirement up front.
If the user's runtime is unsupported, stop before diagnosing individual SFSE plugin failures.
