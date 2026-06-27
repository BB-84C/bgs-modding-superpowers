---
id: load-order.official-cc-as-vanilla-baseline.v1
title: Official Bethesda Creations should be treated as vanilla baseline, not as community mods
kind: rule
domains: [load-order, install-planning]
appliesTo:
  games: [Fallout4, Starfield, SkyrimSE, SkyrimAE]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: "Bethesda's first-party Creations content (Starfield `sfbgs*`, Fallout 4 `ccBGS*`, Skyrim `ccBGS*`) is shipped by Bethesda, signed by Bethesda, auto-managed by MO2's foreign-plugin section, and updated through the same official content pipeline as base-game patches. The right mental model is: it IS part of vanilla, regardless of whether each pack declares a hard ESM master against the base game's `.esm` files. Community mods should be free to override official Creations the same way they override base-game records. Third-party CC content (community mods that happen to be distributed via the Creations storefront, e.g. `kinggath*`, `rbt_*`, `s1n_*`, `caracal_*`) is NOT in this category — those are community mods using Bethesda's distribution channel and should be ordered by community-mod rules. The distinction is authorship and update channel, not where the file came from."
  confidence: high
queryKeys:
  - official CC vs community CC
  - sfbgs as vanilla
  - Bethesda Creations ordering
  - Creation Club load order
  - ccBGS vanilla treatment
  - first-party CC ordering
  - official Creations override semantics
  - MO2 foreign plugin section
  - Creations vs Nexus authorship
  - CC pack ordering rule
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-28 Lane 3 pre-flight sfbgs* relocation reframe — "把官方CC当vanilla处理"
related:
  - mod-evaluation.patch-loads-before-master-heuristic.v1
  - plugin-format.tes4-hedr-master-list.v1
  - install-planning.mod-update-post-state-discipline.v1
lastReviewed: "2026-06-28"
schemaVersion: 1
---

# Official Bethesda Creations should be treated as vanilla baseline, not as community mods

## Perspective: SUBJECTIVE (BB84 curator convention with objective engine grounding)

This rule sits half in objective territory (the engine and MO2 actually manage official CC differently from community plugins) and half in curator convention (the load-order intent that follows from that distinction). The objective half is firm; the curator-intent half should yield to user preference when stated.

## The two categories

Bethesda's Creations storefront distributes two functionally different classes of content under the same label:

**Class A — Official Creations (first-party Bethesda content)**

- Starfield: `sfbgs*.esm` packs (sfbgs009, sfbgs00a_*, sfbgs00b, sfbgs00c, sfbgs00e, sfbgs019, sfbgs021, sfbgs023, sfbgs027, sfbgs028, sfbgs047, ...). Authored by Bethesda or contracted partners under Bethesda's quality bar. Updated as part of the official content pipeline.
- Fallout 4: `ccBGS*` and `ccBGS_BGSSSE*` packs. Same status. Includes the official Creation Club content from the 2019-2021 era.
- Skyrim SE/AE: `ccBGS*` and `ccQDR*` packs. Same status.

**Class B — Community Creations (third-party content distributed via the Creations storefront)**

- Starfield: `kinggath*`, `rbt_*`, `s1n_*`, `caracal_*`, `dwn_*`, `apollo-ll-suite`, `roleplay_backgrounds_expanded`, anything from a Bethesda-recognized creator account that is not Bethesda itself. The plugin file is shipped with a Bethesda signature for storefront integrity, but the authorship and content responsibility are the creator's.
- Same pattern applies to Fallout 4 and Skyrim's community CC tiers.

The same `.esm` file extension, the same MO2 mod folder convention, the same `-cc` suffix in the mod folder name — but two completely different content provenance lanes.

## What follows from the distinction

For **Class A (official Creations)**:

1. The content is effectively a vanilla extension. Bethesda may add records to it, fix bugs in it, or alter its content in future patches without notice. From the modpack's perspective, this content is part of the moving baseline that community mods are designed to override.
2. The right load-order placement is RIGHT AFTER the base game's `.esm` files and Bethesda's own update plugins (e.g. `SFBGS047.esm` for Starfield is Bethesda's content-update plugin and is auto-managed by MO2 in the foreign-plugin section). Place all Class A packs immediately after the auto-managed range, before any community mod.
3. The desired conflict outcome is that community mods WIN over Class A content the same way they win over base-game records. Class A loses to community mods on intentional override surfaces.
4. The order WITHIN the Class A cluster typically doesn't matter — Bethesda designs these packs to be mostly orthogonal. Alphabetical or numeric order is fine.

For **Class B (community Creations)**:

1. The content is community-authored, just like a Nexus mod. The fact that it was distributed via the Creations storefront is a distribution detail, not a quality or trust signal.
2. The right load-order placement follows community-mod rules: framework mods early, content mods mid, patches and overrides late.
3. Conflict outcomes follow the same intent-driven curation as Nexus mods.
4. Order WITHIN the Class B set matters and should be driven by the same conflict-audit reasoning as any other community mod cluster.

## The MO2 foreign-plugin section as confirmation

MO2's auto-detection of "foreign" plugins (managed in the locked section at the top of the plugins panel, priority 0 to ~11 in BB84's Starfield install) already encodes part of this distinction. Base-game `.esm` files (`Starfield.esm`, `Constellation.esm`, `ShatteredSpace.esm`, `OldMars.esm`, `BlueprintShips-Starfield.esm`, `SFBGS003.esm`, `SFBGS006.esm`, `SFBGS007.esm`, `SFBGS008.esm`, `SFBGS027.esm`, `SFBGS028.esm`, `SFBGS047.esm`) live there and are not user-reorderable.

The MO2 design choice to lock these in the foreign section is itself the engine treating them as part of the vanilla baseline. The rule extends that treatment to the rest of Class A (the sfbgs* packs that MO2 happens to expose in the regular section because they came from a Creations storefront download rather than the Steam install): they should behave like the locked-foreign packs even if MO2 doesn't enforce it automatically.

## Why this matters for ordering decisions

Without the Class A vs Class B distinction, a curator faces a confusing question: "should I treat my sfbgs023 (a Bethesda Watchtower-adjacent pack) the same way I treat my kinggathcreations_spaceship (a community Watchtower mod)?" The naive answer "they're both CC content" produces an arbitrary placement.

With the distinction: sfbgs023 goes to Class A (immediately after the auto-managed range, loses to most community mods); kinggathcreations_spaceship goes to Class B (late in the load order, wins over Class A and most community mods).

The placement is no longer arbitrary; it follows from authorship and update channel.

## Identification heuristics

When a curator can't tell whether a `.esm` is Class A or Class B:

- **Plugin filename prefix**: `sfbgs*`, `ccBGS*`, `ccQDR*` → Class A. `<author_handle>_<title>`, `<title>-cc` where the author is a known creator → Class B.
- **Creations page author**: if the author field shows "Bethesda Game Studios" or an official Bethesda account → Class A. If it shows a creator handle → Class B.
- **MO2 mod folder origin**: if MO2 shows the mod with origin `<pack_name>-cc` and the pack name matches a Bethesda numeric scheme → Class A. If the origin reflects an author handle or community name → Class B.
- **Update channel**: Class A is updated alongside official Starfield patches (silently, through the storefront). Class B is updated by individual creators on their own schedule.

## When to deviate

The "official CC = vanilla baseline" rule expresses curator intent. It can be deviated from for specific reasons:

- A specific Class A pack has known bugs that need to be silenced. Move it after a fix-mod that overrides the buggy records.
- The curator wants Class A content to win over a specific community mod for taste reasons. Place that community mod earlier.
- A patch mod between Class A and Class B needs to win over both. Place it after the Class A cluster but before the targeted Class B mod.

The rule sets a default. Curator intent overrides it case by case.

## Concrete illustration

In a 2026-06-27 Lane 3 pre-flight audit, BB84 reframed the earlier-proposed "move each sfbgs* one-by-one based on conflict counts" plan into "move ALL fourteen sfbgs* packs to right after SFBGS047.esm (the last auto-managed foreign plugin), then let every community mod win over them." The reframe collapsed eight separate per-patch ordering decisions into one architectural placement: official CC goes to the vanilla baseline; everything else flows from that.

The orchestrator's earlier framing — "CC as community content competing with other community mods" — produced confused per-conflict decisions because the question itself was malformed. With the Class A/B distinction explicit, the question disappears and the placement becomes obvious.

## See also

- `mod-evaluation.patch-loads-before-master-heuristic.v1` — a related diagnostic for when a "patch" plugin's identity is suspect; complementary to this rule's Class A/B identity distinction.
- `plugin-format.tes4-hedr-master-list.v1` — TES4 header master semantics; relevant for understanding why Class A packs typically declare base-game `.esm` masters cleanly.
- `install-planning.mod-update-post-state-discipline.v1` — covers the intent-vs-effect discipline that this rule applies at the architectural level.
