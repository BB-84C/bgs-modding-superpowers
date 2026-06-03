---
id: papyrus.debug-trace-logging-ini.v1
title: Debug.Trace output depends on Papyrus logging INI settings
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Debug.Trace writes to the Papyrus log only when the relevant Papyrus logging and trace settings are enabled, so missing log lines may be configuration rather than code failure.
  confidence: verified-tooling
queryKeys: [Debug.Trace, Papyrus0.log, bEnableTrace, bEnableLogging, Papyrus logging]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki Trace - Debug
    url: https://ck.uesp.net/wiki/Trace_-_Debug
    sectionPath: Syntax; Parameters
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Debug.Trace output depends on Papyrus logging INI settings

`Debug.Trace` is the right primitive for persistent script logging, but it is not magic.
The CK page ties log output to Papyrus INI settings such as logging and trace enablement.

When a trace is missing, first verify logging configuration and target log path.
Then check whether the event actually fired.

Do not replace trace readback with screen notifications for long debugging sessions.
