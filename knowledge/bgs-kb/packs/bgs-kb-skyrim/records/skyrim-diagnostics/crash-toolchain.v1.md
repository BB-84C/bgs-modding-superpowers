---
id: skyrim-diagnostics.crash-toolchain.v1
title: Skyrim crash diagnostic toolchain
kind: workflow
domains: [debugging]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [SkyrimLE, Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim crash logs are triage evidence, not verdicts: install the logger matching the runtime, read the stack with the current load order, then confirm against recent changes and reproducible in-game routes."
  confidence: high
queryKeys: [Skyrim crash logger, Crash Logger SSE AE VR, NetScriptFramework, SKSE runtime, crash log]
severity: high
sources:
  - kind: tooling-docs
    url: "https://github.com/NetScriptFramework/NetScriptFramework.SkyrimSE"
    ref: ".NET Script Framework Skyrim SE"
  - kind: tooling-docs
    url: "https://github.com/alandtse/CrashLoggerSSE"
    ref: "Crash Logger SSE AE VR project"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/59818"
    ref: "Crash Logger SSE AE VR Nexus page"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Skyrim crash diagnostic toolchain

Pick the crash logger by runtime first. .NET Script Framework is the established Skyrim SE 1.5.97-era logger and ecosystem, while Crash Logger SSE AE VR is the practical baseline for AE and VR runtimes. Do not mix logger advice across SE 1.5.97, AE 1.6.x, GOG AE, and VR without checking the runtime and SKSE family; a crash logger built for the wrong executable can create a false containment breach before the game even reaches the main menu.

Crash logs answer three questions: which executable/runtime crashed, which modules were loaded, and what stack or probable objects were nearby. They do not prove root cause by themselves. A mesh, animation, Papyrus state, memory allocator, or native DLL can surface as a different module in the final stack. Treat the last installed mod, recent patches, and recent load-order changes as high-priority suspects even when the log names something else.

Standard route: reproduce once, save the log, record the active plugins and SKSE DLL set, compare against the last known good profile, then remove or isolate the newest change. If the crash is cell-specific, use a disposable console route to enter the cell; if it is startup-specific, reduce native plugins and ENB/overlay hooks first. Vault seal integrity is only nominal after the same route survives with the suspected fix applied.

For modpack work, archive the log with the profile name and load-order timestamp. A stack trace without the matching plugin list decays quickly: FormIDs, DLL versions, and overwrite winners can all change before another curator reads the evidence.
