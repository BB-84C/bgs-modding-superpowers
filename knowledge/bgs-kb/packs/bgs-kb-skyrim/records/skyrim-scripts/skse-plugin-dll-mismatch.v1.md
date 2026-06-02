---
id: skyrim-scripts.skse-plugin-dll-mismatch.v1
title: SKSE plugin DLLs must be rebuilt for the target Skyrim runtime
domains: [engine, debugging, version-differences]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "When Skyrim starts crashing after a runtime update, SKSE's own guidance points first at Data/SKSE/Plugins DLLs because native plugins are runtime-sensitive."
  confidence: verified-tooling
queryKeys: [SKSE plugin DLL, Data/SKSE/Plugins, AE update crash, runtime mismatch]
severity: critical
sources:
  - kind: tooling-docs
    ref: SKSE silverlock troubleshooting note
    url: https://skse.silverlock.org/
    sectionPath: Startup crash after game patch
related: [engine.xse-plugin-version-compatibility.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SKSE plugin DLLs must be rebuilt for the target Skyrim runtime

SKSE scripts and SKSE native DLL plugins are different risk surfaces.
The DLL plugins under `Data/SKSE/Plugins` bind to runtime-specific addresses or APIs.

When an AE/SE/VR executable changes, do not only update SKSE itself.
Check every SKSE plugin DLL and its Address Library/CommonLib dependency.

If disabling `Data/SKSE/Plugins` fixes startup, the failure is likely native-plugin compatibility rather than Papyrus script source.
