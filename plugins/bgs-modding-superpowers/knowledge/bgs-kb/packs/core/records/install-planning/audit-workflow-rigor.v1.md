---
id: install-planning.audit-workflow-rigor.v1
title: Audit workflow rigor — six disciplines that distinguish thorough audits from surface checks
kind: rule
domains: [install-planning, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: An audit either gives the curator a complete decision-support picture or it gives them noise. Six disciplines separate the two outcomes. Treat each as a hard rule, not a recommendation. The corresponding anti-patterns are silent failures — they look like "investigated" but produce verdicts that the curator catches as wrong in seconds.
  confidence: high
queryKeys:
  - audit workflow rigor
  - investigation discipline
  - never quit on first failure
  - re-validate upstream signals
  - read description fully
  - cross-reference modlist
  - audit workflow methodology
  - mod evaluation rigor
  - fan-out fixer quality
  - orchestrator validation
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-25 audit correction round — six workflow gaps surfaced through user steering
related:
  - install-planning.audit-grade-mod-fate-investigation.v1
  - mod-evaluation.investigating-pulled-mods.v1
  - mod-evaluation.author-version-tag-unsync.v1
  - debugging.asymmetric-evidence-self-falsify.v1
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# Audit workflow rigor — six disciplines that distinguish thorough audits from surface checks

## Perspective: OBJECTIVE

An audit either gives the curator a complete decision-support picture or it gives them noise. The six disciplines below separate the two outcomes. Each is a rule, not a recommendation. Each has been violated in real audit dispatches and produced verdicts the curator caught as wrong within seconds.

## 1. Never quit on first failure — 3+ fallback paths

A failed Nexus API call is not a "not found" verdict. When the user-mods endpoint returns 404, Cloudflare blocks, or a profile page does not render the mod list:

- Try Exa search `site:nexusmods.com/<game>/mods <author_name>`
- Try search by mod name keyword + author handle
- Try the author's external channels (GitHub, Patreon, Discord) where applicable
- Check whether the author maintains a homepage / index mod that lists all their related work

Only after three or more genuinely independent paths fail can the auditor report "not found". The signature of premature give-up is a self-report like "API 404'd, no successor found" appearing within seconds of the API call — there was no fallback attempt.

## 2. Re-validate every upstream classifier signal

Fan-out audits stack multiple classifiers. The orchestrator that consumes their outputs MUST re-validate each label against its own normalized criteria. Trusting the upstream classifier's "Green" or "OK" pass at face value is exactly how classification bugs propagate.

In practice this means: if any lane catches a classifier bug (e.g. version-comparator does not normalize trailing zeros), the orchestrator re-runs the fixed comparator against every other lane's "passed" entries. The bug is rarely lane-local — it is usually a systemic gap.

When a fan-out fixer reports their lane as 80% Green, the orchestrator should treat that as a hypothesis to validate, not a verdict to accept.

## 3. Read descriptions fully, not as regex keyword scans

Author descriptions are stories. Regex keyword matches are blunt instruments that fail on context:

- "Abandoned Farm" matches `abandoned`, but it is a Starfield in-game POI name.
- "Removed by author" matches the regex, but it may be referring to a specific feature that got removed in an update, not the whole mod.
- "DISCONTINUED" matches, but the surrounding paragraph may be the description of an ARCHIVED sub-patch being absorbed into the parent mod, not the parent mod being discontinued.
- Folder names embedding game-version annotation (`Starfield Engine Fixes - Game version 1.16.244`) get scanned as if they were description text — they are not.

The fix is to read the description as prose, not to grep it. When in doubt, surface the matched span to a human reviewer with the surrounding context — never collapse to a Red verdict on regex match alone.

## 4. Cross-reference every recommendation against the actual environment

Recommendations that ignore the curator's installed environment produce noise. Before recommending an optional patch:

- Read `<MO2Root>/profiles/<profile>/modlist.txt` for enabled (`+`) AND disabled (`-`) mods (both count for the patch's future relevance when the curator re-enables CC content).
- Read `<MO2Root>/profiles/<profile>/plugins.txt` for active (`*`) plugins.
- Match the patch's "patches X" claim against the actual installed mod folder names. Do not assume `Useful Brigs` and `Useful Mess Halls` are the same; they are different mods.
- If a recommendation depends on a mod the curator does not have, mark the recommendation as `skip` with the missing-dependency reason.

The pattern that signals weak cross-reference: a list of recommendations to install N patches with no mention of which apply to the curator's actual setup.

## 5. Check ALL file categories — Main, Optional, Update, Archived, Old

For every mod-page investigation, enumerate the FULL file listing:

- **Main** — current canonical builds; often more than one (different variants, game versions, builds).
- **Optional** — compatibility patches, add-ons, alternative variants. Each one carries its own description identifying what it patches.
- **Update** — patches against an earlier Main file, typically requires the Main as prerequisite.
- **Archived / Old** — superseded; sometimes intentionally preserved as fallbacks.

Authors organize file categories to communicate intent. A recommendation that ignores Optional files misses compatibility patches the curator needs. A recommendation that follows Archived files installs superseded content.

For multi-variant Main files (color/size/flavor), surface the variants to the curator as a decision point — do not auto-pick one.

## 6. Surface complete decision space, not boiled verdicts

The curator depends on the audit for decision support, not for a verdict. "X is unusable, replace" closes a door. "X is delisted by author; essence is a four-file texture replacement; cross-referenced against installed mods; local artifact still works under current runtime; recommended action is keep + monitor; alternative is replacement candidate Y if curator prefers" opens an informed choice.

Surface:

- The full essence analysis (file count, type breakdown, classification)
- The continuity tracing outcome (republished / off-Nexus / dead / etc.)
- The cross-reference against the curator's actual modlist
- Multiple recommended actions when applicable, not a single boiled verdict
- The supporting evidence per claim, so the curator can sanity-check fast

The pattern that signals weak surfacing: a single-line `Red, find replacement` verdict with no underlying evidence chain that the curator can sanity-check.

## Why this matters

The cost difference between a rigorous audit and a surface audit is enormous for the curator. A surface audit produces 50 Red verdicts requiring investigation; the rigorous version separates the 4 real problems from the 46 false positives. The cost difference between rigorous and surface for the auditor is small — a few additional API calls and a few more minutes of reading per mod. The trade is decisively in favor of rigor.

This rule exists because the audit dispatch that triggered it produced ~50 surface Red verdicts that the curator manually corrected within minutes, then asked for the workflow methodology to be codified so future audits start at the rigorous baseline instead of needing to be steered there.

## See also

- `install-planning.audit-grade-mod-fate-investigation.v1` — the outcome shape (4+ fate verdicts vs binary "unusable").
- `mod-evaluation.investigating-pulled-mods.v1` — continuity tracing technique used inside discipline 1.
- `mod-evaluation.author-version-tag-unsync.v1` — file-vs-page version comparison used inside discipline 5.
- `debugging.asymmetric-evidence-self-falsify.v1` — the analogous discipline applied to diagnostic asymmetry, not audit classification.
