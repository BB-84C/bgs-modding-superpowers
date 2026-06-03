---
id: tooling-mo2.wabbajack-modlist-install-model.v1
title: Wabbajack installs declared modlists from manifests and source downloads
domains: [install-planning, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, FalloutNV]
canonical:
  answer: Wabbajack is an automated modlist installer that uses a manifest and source downloads to reproduce a curated setup, rather than being a generic loose collection of plugin edits.
  confidence: verified-tooling
queryKeys: [Wabbajack, modlist installer, manifest, Nexus API, automated modlist]
severity: medium
sources:
  - kind: tooling-docs
    url: "https://wiki.wabbajack.org/"
    ref: Wabbajack documentation wiki
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Wabbajack installs declared modlists from manifests and source downloads

Wabbajack distributes a reproducible install plan, not the full set of third-party mod files as one opaque archive.
Its documentation emphasizes manifests, download sources, and installer behavior that retrieves files from places such as Nexus via supported APIs.

For agents, the modlist manifest is the artifact to inspect first.
Do not treat a Wabbajack install failure as merely a plugin load-order problem.
