---
id: tooling-mo2.mutagen-typed-record-api.v1
title: Mutagen exposes typed Bethesda records for programmatic patchers
domains: [tooling.mutagen, plugin-format, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Mutagen is a C# library for reading and writing Bethesda plugins through typed record APIs, making it a good substrate for programmatic patchers when xEdit daemon semantics are not required.
  confidence: verified-tooling
queryKeys: [Mutagen, typed records, C# patcher, WinningOverrides, programmatic patch]
severity: high
sources:
  - kind: tooling-docs
    url: "https://mutagen-modding.github.io/Mutagen/"
    ref: Mutagen documentation
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Mutagen exposes typed Bethesda records for programmatic patchers

Mutagen presents Bethesda plugin data through generated typed APIs, which lets patcher code reason about record classes rather than raw bytes.
Its examples use game-specific release selection and load-order environments before reading winning overrides.

Use this when building a real patcher or serializer workflow.
For live harness state, conflict audits, or xEdit-specific semantics, keep using the xEdit MCP instead of bypassing it.
