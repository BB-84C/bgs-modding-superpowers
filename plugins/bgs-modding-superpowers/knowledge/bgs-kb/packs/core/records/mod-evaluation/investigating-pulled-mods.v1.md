---
id: mod-evaluation.investigating-pulled-mods.v1
title: Pulled-mod investigation as continuity tracing
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "A Nexus status of not_published / hidden / removed is a continuity clue, not an immediate death verdict. Investigate from the smallest-distance continuity hypothesis outward: same-author republish under a new modid, same-author continuation off Nexus, third-party maintenance fork, then unrelated replacement. If continuity is found, reconcile MO2 metadata such as meta.ini modid and installationFile so the local mod tracks the live lineage rather than the orphaned listing."
  confidence: high
queryKeys: [pulled mod, hidden mod, not_published, removed mod, author republish, status=hidden, status=not_published, dead modid, modid drift, mod taken down, find alternative]
severity: high
sources:
  - kind: project-internal-doc
    url: "https://github.com/BB-84C/bgs-modding-superpowers/blob/main/docs/modpack-dev-logs/bb84-starfield/dev-log.md"
    ref: "2026-06-24 round-2 dev-log section 'P2-pulled-mods'"
  - kind: official
    url: "https://app.swaggerhub.com/apis-docs/NexusMods/nexus-mods_public_api_params_in_form_data/1.0"
    ref: "Nexus public API mods/{modid}.json status field semantics"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Pulled-mod investigation as continuity tracing

A Nexus status such as `not_published`, `hidden`, or `removed` is not a verdict that the mod is dead. It is a signal that one listing no longer behaves like a normal live listing. The investigation question is therefore not "what replacement do we choose?" but "where did this author's intent and the mod's lineage go?"

Treat author intent as substrate to investigate. A mod may be deliberately discontinued, temporarily hidden, republished under a fresh modid, moved to an external release channel, or superseded by a community-maintained fork. Each outcome implies a different curator action, so the first job is continuity tracing.

## Smallest-distance continuity first

Use an expanding-radius investigation order:

1. **Same author, new modid** — the closest continuity hypothesis. The author may have restarted the listing while preserving name, description, files, or feature intent. Use the original `author` and `user.member_id`, search for the same or near-same mod name, inspect the author's profile, and confirm candidate continuity by matching `user.member_id` through the Nexus API.
2. **Same author, off-Nexus continuation** — if the Nexus lineage truly stopped, check whether the author moved releases or source to GitHub, Patreon, Discord, or another linked channel.
3. **Third-party maintenance fork** — if the original author stopped, look for permission-compatible community continuations using search terms such as "continued", "updated", "patched", or game-runtime-specific variants.
4. **Alternative implementation** — only after continuity paths fail, search for another author's mod that solves the same user-facing problem, accepting that it may use a different technical approach.

This order matters because each step is farther from the original intent and usually more expensive to evaluate. Same-author republish often preserves the most semantics for the least curator effort. Alternative implementations may be necessary, but they should not be the first reflex.

## Modid drift is lineage drift in metadata

MO2 tracks Nexus lineage through `meta.ini` fields such as `modid=` and `installationFile=`. When an author republishes under a new modid, a previously installed mod folder can keep pointing at the orphaned listing even after the curator manually installs files from the live listing. The local content and the metadata lineage have diverged.

The breadcrumb is often the archive filename: Nexus-generated names may include both old and new identifiers, or otherwise reveal that the installed archive came from a different listing than `meta.ini modid=` claims. When continuity tracing proves a new live listing is the correct lineage, reconcile `meta.ini modid=` and `installationFile=`, then refresh update state so `newestVersion`, `lastNexusQuery`, and `lastNexusUpdate` come from the live listing rather than the orphaned one.

The principle is not "always edit modid when status is hidden." The principle is: once investigation proves lineage moved, local metadata must be moved to the same lineage or every future update check will keep reporting the abandoned branch.

## Dev-log discipline

Record the investigation in the modpack project's `docs/dev-log.md`:

- original mod name, modid, status, author, and `user.member_id`;
- which continuity radius succeeded or failed;
- the decision: re-track new modid, keep and monitor, follow external continuation, switch fork, switch alternative, or disable;
- any metadata reconciliation performed.

This preserves the reasoning, not just the result, so future maintenance does not re-run the same investigation from scratch.

## Illustrations, not shortcuts

- CharGenMenu's old Nexus #20 listing reported `not_published`, but the same author republished the same feature lineage as #6850. The right fix was lineage reconciliation, not replacement search.
- Weapon Swap Stuttering Fix #2830 was hidden without an obvious same-author republish; an unrelated mod used a perk-based alternative rather than the original SFSE-DLL approach. That is a later-radius answer, not the default first move.

For curators, the cost difference is large: continuity tracing may end in a small metadata correction, while premature replacement search can require a new risk evaluation, installation path, compatibility pass, and rollback story.
