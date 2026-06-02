---
id: papyrus.debug-notification-is-ui-not-log.v1
title: Debug.Notification is transient UI, not durable script logging
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Debug.Notification displays an on-screen message, but it is transient UI and has formatting caveats; use Debug.Trace for durable Papyrus diagnostics.
  confidence: verified-tooling
queryKeys: [Debug.Notification, notification, Papyrus UI debug, angle brackets]
severity: low
sources:
  - kind: wiki
    ref: Creation Kit Wiki Notification - Debug
    url: https://ck.uesp.net/wiki/Notification_-_Debug
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Debug.Notification is transient UI, not durable script logging

`Debug.Notification` is useful for quick visible feedback, not for audit-quality diagnostics.
The CK notes also document formatting caveats around angle brackets in notification text.

Use `Debug.Trace` when the evidence needs to survive as a log.
Use notifications sparingly so debugging does not become a UI flood.

For automated acceptance, prefer log/readback artifacts over screen-only messages.
