---
id: mod-evaluation.conflict-count-vs-behavior-impact.v1
title: File-level conflict counts mislead in BOTH directions about behavior-impact scope
kind: rule
domains: [install-planning, file-conflicts, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: |
    A mod's file-level conflict count is one signal among five, not the decision. The same file count can hide either NEAR-ZERO behavior impact (a single companion's voice bank that wins 2000+ files) or HIGH mainstream-vanilla impact (a quest pacing mod that touches 15+ vanilla quest records but only wins 8 files). The correct pre-flight rubric is bidirectional — separately classify scope (mainstream-vanilla vs niche-narrow vs infrastructure vs cosmetic-replacer), impact tier, save-bake risk, vanilla-script-modification, and conflict-overestimation direction (HIGH-COUNT-LOW-IMPACT vs RAW-COUNT-MATCHES-IMPACT vs LOW-COUNT-HIGH-IMPACT). A small framework that touches mainstream vanilla quest aliases is more dangerous than a 2000-win cosmetic replacer.
  confidence: high
queryKeys:
  - conflict count misleads
  - behavior impact scope
  - mainstream vs niche
  - file count vs behavior
  - conflict overestimation
  - low count high impact
  - high count low impact
  - lane 3 pre-flight rubric
  - mod risk assessment
  - bidirectional conflict rubric
  - vanilla quest record impact
  - companion voice replacement scope
  - SFSE extender scope
severity: high
sources:
  - kind: project-internal-doc
    url: https://github.com/BB-84C/bgs-modding-superpowers/blob/main/docs/modpack-dev-logs/bb84-starfield/dev-log.md
    ref: BB84 2026-06-27 Lane 3 pre-flight v3 — VASCO-9000 / No Sound In Space / Cassiopeia Papyrus Extender hypothesis confirmation + Take Your Time / ELFX / Dark Universe trio inversion cases
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-preflight/report-v3.md — 34-mod 4-way fan-out classification with file-system evidence
related:
  - mod-evaluation.systemic-design-fit.v1
  - mod-evaluation.quality-and-risk-signals.v1
  - install-planning.numeric-fetish-anti-signal.v1
  - pack-curation.pre-install-prediction-discipline.v1
  - papyrus.vanilla-script-modification-red-flag.v1
  - starfield-save-hygiene.script-baking.v1
lastReviewed: "2026-06-27"
schemaVersion: 1
---

# File-level conflict counts mislead in BOTH directions about behavior-impact scope

## Perspective: OBJECTIVE

## The trap of count-as-decision

When inspecting a modpack's MO2 conflict view or a tool-generated conflict report, the easy reflex is to sort by win count and treat the top of the list as "highest risk". This produces wrong calls in two opposite directions.

A mod can win 2053 files and have NEAR-ZERO behavior impact: VASCO-9000 Voice Replacement (2053 `.wem` wins) replaces one robot companion's voice bank — all 2053 files live in one directory (`sound/voice/starfield.esm/robotmodelavasco/`). There is no plugin, no script, no quest. The scope is exactly one companion.

A mod can win 8 files and have HIGH mainstream-vanilla impact: Take Your Time (8 wins) modifies start conditions on 15+ vanilla quest records spanning the main quest, all faction starters, and DLC content. The 8-win count understates impact by an order of magnitude because each touched QUST is a structural edit on the narrative skeleton, not a cosmetic replacement.

Sorting by count gets these exactly backwards. The 2053-win mod becomes the audit headline and the 8-win mod gets skipped.

## The bidirectional rubric

Classify each mod across five orthogonal signals:

1. **Scope** — `mainstream-vanilla` (vanilla quest / faction / combat / economy / main-loop systems) vs `niche-narrow` (own subsystem with limited surface) vs `infrastructure` (framework or SFSE plugin consumed by other mods) vs `cosmetic-replacer` (textures / sound / UI assets).
2. **Impact tier** — `HIGH` / `MEDIUM` / `LOW` / `NEAR-ZERO`, derived from scope plus blast radius.
3. **Save-bake risk** — `high` / `medium` / `low` / `none`, per `starfield-save-hygiene.script-baking.v1` and analogous per-game KB records. Frameworks with active quests, aliases, or persistent script state are HIGH; pure asset replacers are NONE.
4. **Vanilla-script-modification** — `yes` / `no` / `unclear`. Yes when loose `.pex` files at `scripts/X.pex` match real vanilla script names (Actor, ObjectReference, Quest, faction-specific scripts) OR when archived scripts shadow vanilla names. This is the structural red flag from `papyrus.vanilla-script-modification-red-flag.v1`.
5. **Conflict-overestimation** — the direction of file-count misreading:
   - `HIGH-COUNT-LOW-IMPACT` — count overestimates risk (VASCO-9000, No Sound In Space, cosmetic skin packs, UI replacers, single-author asset bundles)
   - `RAW-COUNT-MATCHES-IMPACT` — count broadly tracks risk (most mods)
   - `LOW-COUNT-HIGH-IMPACT` — count underestimates risk (Take Your Time, Ship Vendor Framework with 4 vanilla script overrides, Dark Universe Overtime hooking Story Manager)

The decision flows from the combined signals, not from count alone.

## File-count overestimation signatures

The HIGH-COUNT-LOW-IMPACT case is identifiable from substrate inspection:

- **Single-directory voice-bank**: all wins under one `sound/voice/<plugin>/<actor>/` directory → one NPC's voice replacement, narrow.
- **Single-soundbank-directory swap**: all wins under `sound/soundbanks/` for one audio system (space combat, ambient music, UI feedback) → one SFX layer.
- **Single-namespace asset bundle**: meshes/textures all under `meshes/clothes/<modname>/` or `textures/clothes/<modname>/` → standalone craftable, no vanilla override.
- **Per-author UI replacement**: `.swf` / `.gfx` / `.css` / `.js` files in `interface/` for one author's UI overhaul → menu replacement, no behavior.
- **Sibling cosmetic packs by one author**: four UCMO-style skin packs that override each other on 10-20 records — by design, not redundancy.
- **SFSE Address Library / versionlib offset databases**: `.bin` files in `sfse/plugins/` consumed by other DLL plugins → infrastructure, no behavior.

When these signatures hold, file count is not the right signal. Behavior impact is low or zero regardless of the win number.

## File-count underestimation signatures

The LOW-COUNT-HIGH-IMPACT case requires reading the description and inspecting the plugin file:

- **Small framework ESM with vanilla-script overrides**: a 5-10 MB `.esm` with a handful of file wins but overrides vanilla Papyrus scripts (e.g., `Ship Vendor Framework` overriding `ShipVendorScript`, `ShipBuilderMenuActivator`). Vanilla script override is the structural red flag.
- **Quest pacing / quest start-condition framework**: tiny file footprint but the description names mainstream vanilla quests (main quest, all faction starters). The author's description is the data — Take Your Time names 15+ touched quests.
- **Story Manager / mission-board / quest-marker injection**: framework adds new quests but hooks vanilla Story Manager (SMQN), quest-marker (PCM), or mission-board surface. The hook surface is mainstream even if file count is small.
- **Companion-state / affinity / dialogue routing framework**: handful of plugin records but touches companion-state systems (affinity, dialogue, faction membership, locked-in quest follower behavior).
- **Interior cell lighting with ESM**: the asset wins look small but the shipped ESM carries INTR overrides for mainstream-tour cities (Lodge, New Atlantis, Akila, Cydonia, Neon) and overlaps with other lighting mods.

When the description names vanilla systems or the file inventory shows a non-trivial ESM with low asset wins, suspect underestimation.

## When the rubric applies

This rubric is for **Lane 3 pre-flight reconnaissance** — substrate-based behavior classification BEFORE xEdit FormID-level audit. It produces audit priorities, not final verdicts.

- Pre-flight produces a priority queue. xEdit Lane 3 proper enumerates records and verifies claims.
- The rubric ranks where xEdit time is best spent. LOW-COUNT-HIGH-IMPACT mods are priority 1 because file inspection alone cannot verify their no-override claims.
- Cosmetic-replacers and infrastructure with confirmed-narrow scope can be skipped at the xEdit stage entirely.

## Operational pre-flight workflow (the substrate-selection corollary)

The bidirectional rubric implies a workflow: BEFORE the heavy xEdit audit work, run a **pre-flight reasoning audit** on the modlist and plugin order, using description + KB heuristics, to PRE-ORDER the substrate. This dramatically reduces the work xEdit has to do, because mods already classified as cosmetic-replacer or confirmed-narrow infrastructure can be skipped at the FormID-level stage.

### Substrate selection (do not cut at top-N file wins)

When building the substrate for pre-flight reconnaissance, **do not** sort the mod list by file conflict count and take the top-N. That selection method systematically misses the LOW-COUNT-HIGH-IMPACT bucket — exactly the cluster the rubric warns against. The same rubric that classifies "8 wins, mainstream impact" mods as priority 1 is violated at the substrate stage if those mods are not included in the investigation list at all.

The correct substrate selection rule:
- Include **every enabled mod whose description names a mainstream-vanilla system** (quests, factions, combat, economy, ship systems, oxygen/fuel/survival systems, companion/crew systems), regardless of file count.
- Include **every systemic mechanism mod** — frameworks adding survival mechanics, fuel mechanics, medical systems, economy layers, crew management — regardless of file count.
- Include **the author's own listed compatibility patches and disabler ESMs** — if a mod ships a `Disabler.esm` for a specific subsystem, that ESM names the conflict surface explicitly.
- Then add the top-N file-conflict winners as a SECONDARY input. The file-count signal still matters for asset-conflict resolution; it just must not be the only basis for inclusion.

### Pre-flight reasoning audit on modlist and plugin order

Two distinct audit substrates feed Lane 3 proper:

1. **modlist.txt audit** (asset / left-pane order): each mod's priority should reflect file-conflict winners. Mods that override another mod's assets must load after (higher priority) the mod they override. Mods without file conflicts should default to alphabetic order within their category separator. Translation siblings (`- SC`, `- CHN`, `- DE`, etc.) must follow their parent mod immediately. Mis-categorized mods (wrong separator) should be flagged for relocation. The substrate produced here is a proposed modlist.txt reorganization with rationale per mod.

2. **plugins.txt audit** (record / right-pane order): each ESM's load order should reflect record-override winners, inferred from KB heuristics PRE-xEdit. Use: (a) `papyrus.script-impact-scope-inference.v1` to infer per-ESM behavior scope from the origin mod's classification; (b) the bidirectional rubric here to assess if a small ESM hides mainstream-vanilla impact; (c) author-documented load-order rules from descriptions when available. The substrate produced here is a proposed plugins.txt order with rationale per ESM, plus a list of "ordering cannot resolve this — patch needed" cases flagged for Lane 3 xEdit work.

### The phase-separation discipline

The pre-flight reasoning audit is a phase of its own — distinct from xEdit FormID audit. Doing the modlist+plugins ordering inference first means:

- xEdit work focuses on cases where ordering is genuinely insufficient (record-merge patches needed, conflict-resolution patches needed).
- Mods classified as confirmed-narrow or cosmetic don't consume xEdit time.
- The proposed ordering itself is an artifact: future curator updates can be compared against the rationale to detect regressions.
- The phase separation makes it visible WHICH decisions need empirical FormID verification vs. which can be settled by reasoning.

### Workflow shape (in practice)

1. Audit the modlist: build the substrate selection list per the rule above.
2. Classify each substrate mod with the bidirectional rubric (this record's five signals).
3. Build modlist.txt audit substrate: per-mod proposed separator + priority + rationale.
4. Build plugins.txt audit substrate: per-ESM proposed load order + rationale + "patch needed" flags.
5. ONLY THEN start xEdit FormID work on the flagged cases.

The substrate artifacts (audit reports) become the inputs to Lane 3 proper. They are also the artifacts a future curator can inspect when something in the pack regresses — the rationale chain is preserved, not just the final order.

## Anti-patterns

- **Top-of-conflict-list = top audit priority**. False. VASCO-9000 at 2053 wins is priority 5 (skip). Take Your Time at 8 wins is priority 1.
- **No vanilla `.pex` override claim from author = safe**. False. Author claims need verification when the framework hooks Story Manager, mission boards, faction relationships, or quest aliases. Mark `unclear` until xEdit confirms.
- **File-system inspection is enough for framework mods**. False. Framework mods package scripts inside BA2; loose-file scan misses them. Use the description + Nexus Q&A + xEdit BA2 enumeration.
- **Skipping the description and going straight to xEdit**. Wasteful. The description names which vanilla systems the author claims to touch — that's the prior xEdit should test, not derive from scratch.

## Cross-reference

- `mod-evaluation.systemic-design-fit.v1` — the systemic design lens that scope classification implements.
- `papyrus.vanilla-script-modification-red-flag.v1` — vanilla-script-modification structural red flag (the 4th rubric signal).
- `starfield-save-hygiene.script-baking.v1` (and analogous per-game records) — save-bake risk (the 3rd rubric signal).
- `install-planning.numeric-fetish-anti-signal.v1` — the broader "count is not quality" pattern applied to whole packs; this rubric is its per-mod equivalent.
- `pack-curation.pre-install-prediction-discipline.v1` — pre-install blast-radius prediction; this rubric is its post-install / mid-pack audit shape.
