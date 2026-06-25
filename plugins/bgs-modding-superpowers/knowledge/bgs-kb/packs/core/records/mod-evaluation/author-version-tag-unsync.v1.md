---
id: mod-evaluation.author-version-tag-unsync.v1
title: Nexus mod-page version and file version are independent and routinely desync
kind: gotcha
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: A Nexus mod listing carries TWO independent version fields — the mod-page "Version" displayed at the top of the page, and the per-file `version` recorded against each uploaded archive. The two are independently maintained by the author. When an author uploads a newer file without bumping the page header, the page-version becomes stale while the file-version is the real latest. Agents auditing staleness must compare against the latest Main file's `version`, NOT the page header. Investigation signal: when MO2's installed version is greater than the Nexus page-version, this is almost always a page-version desync rather than a fork or downgrade.
  confidence: high
queryKeys:
  - Nexus page version vs file version
  - mod page version stale
  - installed greater than latest
  - author forgot to bump version
  - version tag desync
  - mod-page version unsync
  - file_id version vs page version
  - VERSION-TAG-UNSYNC
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-25 audit — Immersive Star Colours (#14274) installed 1.1 vs page 1.0; Shader Injector (#5562) installed 1.10 vs page 1.9; SKKFastStartNewGame (#5971) installed 14 vs page 15 vs file 017
  - kind: tooling-docs
    ref: Nexus public API mods/{modid}.json `version` field is mod-page-version; mods/{modid}/files.json each file has its own `version` field maintained separately
    url: https://app.swaggerhub.com/apis-docs/NexusMods/nexus-mods_public_api_params_in_form_data/1.0
related:
  - install-planning.audit-grade-mod-fate-investigation.v1
  - mod-evaluation.investigating-pulled-mods.v1
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# Nexus mod-page version and file version are independent and routinely desync

## Perspective: OBJECTIVE

The Nexus mod-page version field and the per-file version field are independent edit surfaces for the author. There is no automation that propagates one to the other.

## The mechanism

When an author publishes a new build:

1. They upload the new archive (Main / Optional / Update category) — Nexus records a per-file `version` and `uploaded_timestamp` automatically.
2. They are supposed to also edit the mod-page Version field at the top of the page, which is the field shown in the page header, in Nexus search results, in the public mods endpoint `version` field, and in MO2's `newestVersion` field after `setNewestVersion` is called.

The second step is manual and easily forgotten. Many authors update only the file and miss the page header. Some never update the page header at all and rely on file version stamps.

The result is three independent version surfaces:

- **Mod-page Version** (page header, public API `mods/{modid}.json#version`): author-edited string, may be stale.
- **Per-file version** (each file's `version` field on `mods/{modid}/files.json`): set automatically by Nexus from the uploader's input; the latest Main file's version is the real authoritative latest.
- **MO2 installed_version** (`meta.ini#version`): the version of the archive currently installed; may be ahead of, equal to, or behind the file the curator has on disk depending on how MO2 tracked it.

## The diagnostic signal

The strongest signal for page-version desync is `installed_version > page_version`. A curator's installed version cannot be higher than the latest published file unless they have a private build (rare). So when the audit reports `installed > page_version`, the working hypothesis is:

1. Author uploaded a newer file but forgot to bump the page header.
2. Look at the latest Main file's `version` field on the files endpoint.
3. If file `version >= installed`, this is page-version desync. Keep installed; no action.
4. If file `version < installed`, this is a real fork or private build.

Even when `installed_version < page_version`, the file endpoint check is still the correct authoritative comparison. Compare the curator's `installed_version` against the latest Main file's `version`, not the page header.

## The implication for audits

Naive staleness audits that compare MO2's installed_version against the public API's mod-level `version` field will produce false positives any time the author forgot to bump the page. In practice this is common — three of the cases that triggered this rule's codification were all version-tag desyncs:

- Immersive Star Colours (#14274) — page 1.0, file 1.1, installed 1.1 — installed matches the real latest.
- Starfield Shader Injector (#5562) — page 1.9, latest file 1.10, installed 1.10 — installed matches the real latest.
- SKKFastStartNewGame (#5971) — page 15, latest file 017, installed 14 — installed is actually behind the real latest.

The third example also shows the inverse case: even when `installed < page_version`, the real latest may differ from both. Always reach for the files endpoint.

## The audit fix

Replace the page-version comparison with file-version comparison everywhere:

- Don't compare `mod.version` (page) to `meta.ini#version` (installed).
- Do compare `files.files[*].version` where `category == "main"` and sort by `uploaded_timestamp` descending — the top entry is the real latest.
- For multi-variant Main releases (e.g. SFSE vs GamePass ASI builds, or fork-flavored builds), pick the variant matching the curator's environment before comparing.

## See also

- `install-planning.audit-grade-mod-fate-investigation.v1` — the broader audit-grade discipline; file-version checks are part of "audit-grade rigor".
- `mod-evaluation.investigating-pulled-mods.v1` — for pulled mods, both page and file versions are mostly unavailable; continuity tracing applies instead.
