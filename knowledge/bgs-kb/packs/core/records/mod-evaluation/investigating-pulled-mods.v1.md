---
id: mod-evaluation.investigating-pulled-mods.v1
title: Investigating Nexus mods marked not_published / hidden / removed — author republish is the priority check
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "When a Nexus mod's API status is not_published / hidden / removed, FIRST check whether the same author republished the mod under a new modid (this is a real modder habit), THEN check third-party maintenance forks, THEN search for alternative implementations by other authors. Do not jump to disabling or finding replacement before exhausting the author-republish check. Also update the MO2 mod folder's meta.ini modid to the new listing once found — otherwise Option B refresh continues reporting the dead status."
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

# Investigating Nexus mods marked not_published / hidden / removed — author republish is the priority check

When the agent (or a MO2 update-check pass) reports a mod as `status=not_published`, `status=hidden`, or `status=removed`, the default reflex is to suggest "disable it" or "find replacement". That reflex misses a real curator pattern: SOME MODDERS RESTART with a fresh modid instead of updating in place. The "dead" modid is just an abandoned listing; the actual mod is alive at a different modid, often with the same name, by the same author. Jumping to replacement search before checking the author's other current mods means missing the obvious continuation.

## Investigation order (do these in this sequence)

1. **Same author, new modid (republish check)** — this is the highest-yield step.
   - Get the original mod's `author` + `user.member_id` from `/v1/games/{game}/mods/{modid}.json`.
   - Search Nexus listings for the same `name` — the new modid is often visible in any search result that pre-dates the takedown (Exa search `"<mod name>" Nexus <game>` typically surfaces both old and new modids).
   - Visit the author's profile page (`uploaded_users_profile_url`) and look for mods with similar names.
   - Confirm by fetching the candidate new modid via API and matching `user.member_id`.
   - Real case (BB84 2026-06-24): CharGenMenu Nexus #20 was `not_published` (Expired6978), but the same author REPUBLISHED as #6850 at v1.1.0.22 with the same description and feature set. The MO2 mod was tracking #20 forever and the refresh kept reporting `not_published`.
2. **Same author, GitHub / Patreon / Discord continuation** — if the Nexus listing is truly gone, some authors continue on GitHub source or Patreon. Check the original mod's description footer for source links, the author's Nexus profile for external links, and the community wiki.
3. **Third-party maintenance fork** — Some popular mods get unofficial maintenance forks by other modders after the original author goes quiet. Check Nexus search for the mod name + words like "continued", "updated", "patched". Beware permission ambiguity if the original author hasn't granted continuation rights.
4. **Alternative implementations by other authors** — only AFTER steps 1-3 fail to find a continuation. The replacement may use a completely different approach (e.g., perk-based vs SFSE-plugin-based for the same UX issue). Real case (BB84 2026-06-24): Weapon Swap Stuttering Fix #2830 was author-hidden; no republish; alternative #16464 by `melik173` uses a perk-based fix instead of the original SFSE-DLL approach.

## meta.ini modid drift caveat

When a mod has been republished (old modid → new modid) and the MO2 user originally installed from the OLD modid, the MO2 mod folder's `meta.ini` `modid=<old>` will continue referencing the dead listing forever. Symptoms:

- `Tools → Check All for Updates` or Option B refresh reports `status=not_published` repeatedly.
- The mod itself is fine in-game (it was working before).
- The user may have manually downloaded the new version from the new modid but the mod folder's meta.ini wasn't updated.

Fix: edit `meta.ini` `modid=` to the new modid AND `installationFile=` to the new archive name (the archive filename usually embeds the modid: `CharGen v1-1-0-20-6850-1-1-0-20-1754930264.7z` shows the new modid `6850` in the second numeric segment). After the modid update, run Option B refresh again to populate `newestVersion`, `lastNexusQuery`, `lastNexusUpdate` from the live listing.

## Dev-log discipline

Every pulled-mod investigation should be recorded in the modpack project's `docs/dev-log.md`:

- Mod name + original modid + status
- Author + user.member_id
- Outcome of investigation steps 1-4 (which step succeeded, what was found)
- The decision (modid update / keep + monitor / switch alternative / disable)

This makes the half-year-later question "why did we switch X to Y?" answerable without re-investigating.

## Why this matters

For modpack curators, the difference between "mod gone, switch to replacement" and "author republished, just retrack" is the difference between a 30-minute investigation + reinstall + verify cycle vs a 2-line meta.ini edit. Without the discipline of checking author republish FIRST, the curator pays the heavier cost every time.
