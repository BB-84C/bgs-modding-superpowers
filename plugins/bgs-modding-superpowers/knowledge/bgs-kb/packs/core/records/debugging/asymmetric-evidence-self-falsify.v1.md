---
id: debugging.asymmetric-evidence-self-falsify.v1
title: Falsify the asymmetry observation before letting it falsify the simple hypothesis
kind: rule
domains: [debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: When two states show different outcomes and the difference is being used to falsify a simple hypothesis, first verify that the two observations are actually comparable. "A is broken, B is fine, therefore the cause is in their difference" only holds if A and B were observed under the same conditions. Asymmetric evidence is psychologically compelling and tends to escalate diagnosis toward complex hypotheses — but if the asymmetry itself is an artifact of sloppy comparison, the escalation is wasted effort.
  confidence: high
queryKeys:
  - asymmetric evidence
  - falsifying hypothesis
  - diagnostic discipline
  - profile comparison
  - empty profile baseline
  - observation comparability
  - modpack diagnostic methodology
  - cheap test first
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 2026-06-25 same-save asymmetric observation misled diagnosis toward mod-overlay hypothesis when stale CK extract was the simpler root cause
related:
  - archive-precedence.stale-ck-extract-loose-files.v1
  - install-planning.mod-update-post-state-discipline.v1
lastReviewed: "2026-06-25"
schemaVersion: 1
---

# Falsify the asymmetry observation before letting it falsify the simple hypothesis

## Perspective: OBJECTIVE

A diagnostic chain has two failure modes. The cheap failure mode is jumping to the first plausible cause and not testing it. The expensive failure mode is over-trusting a piece of evidence that argues against a simple cause, and using it to escalate into a complex investigation that did not need to happen.

This rule is about the expensive mode.

## The trap

The empty-profile baseline is a powerful diagnostic primitive (`diagnosing-bgs-problems` empty-profile-baseline). It is also routinely misused. When a curator observes "the heavy-modded profile shows symptom X, the empty test profile does not", the natural reading is "X is caused by something in the mod set, since the only difference between the two states is the mod overlay". That reading is correct only if the comparison is actually clean.

In practice, comparison cleanliness is brittle. A few real-world failure modes:

- The test profile loaded the same save but did not actually walk to the scene where the symptom manifests
- The test profile loaded under a different shader cache state, masking the otherwise-visible artifact
- The user-visible report on the test profile ("looks fine") was about a different surface than the report on the broken profile
- The game session that observed the test profile cleared a runtime cache that the broken profile never cleared
- The two observations happened in different rendering states (post-load vs mid-session, day vs night, interior vs exterior)

When any of these are true, the asymmetry is comparison artifact, not signal.

## The discipline

When asymmetric evidence appears and seems to falsify a simple hypothesis, run one cheap check before escalating:

- Can both observations be confirmed to be observations of the same surface, under the same conditions, with the same in-game state?
- If yes, the asymmetry is real and the simple hypothesis is genuinely weakened.
- If no, the asymmetry has not been established. The simple hypothesis is still a cheap test to run.

The cost asymmetry justifies the discipline. Testing the simple hypothesis (often a single filesystem operation, INI line check, or fixture inspection) is typically minutes. Acting on falsified asymmetric evidence and escalating into mod bisection, multi-perspective consultation, or deep tooling work is typically hours to days.

The discipline does not mean "ignore asymmetric evidence". It means "treat asymmetric evidence as a hypothesis itself, and verify the hypothesis before using its output".

## The hierarchy

The hierarchy for any modded-BGS diagnostic:

1. **Run the cheapest plausible test first.** Stale loose files, INI corruption, missing masters, archive invalidation toggles, game integrity verification.
2. **Empty-profile baseline.** With explicit verification that both observations are of the same surface and state.
3. **Mod overlay bisection.** Mass disable, binary search, isolate by separator.
4. **Deep tooling.** xEdit conflict audit, Trainwreck stack reading, Papyrus log forensics.

The asymmetric-evidence-self-falsify rule lives between step 1 and step 2. If the curator's empty-profile baseline (step 2) returns "broken vs fine" but step 1 has not been exhausted, the simple causes are still on the table. The asymmetry was not strong enough to skip them.

## Concrete illustration

In a 2026-06-25 audit, a curator's heavily-modded Starfield profile rendered purple terrain at New Atlantis after the 1.16.244 game patch. A near-empty test profile rendered the same save without visible breakage. The diagnostic agent treated the asymmetric observation as falsification of the simple "stale Creation Kit loose materials" hypothesis (which would imply both profiles should break, since they share the same game-install loose files). The agent escalated toward "the root cause has a mod-overlay component, so we must bisect 245 mods".

In fact, deleting the stale `Data\Materials\` alone fixed the heavily-modded profile entirely. The test-profile observation was almost certainly a comparison artifact — the curator likely had not walked to the same New Atlantis location in the test profile, or had loaded under a different rendering state. The asymmetry was not real signal.

Cost of the failure mode: hours of planning, a near-launch of mass mod disable, and several rounds of investigation framing. Cost of testing the simple hypothesis first: one `Remove-Item -Recurse -Force` on a known-recoverable directory.

## See also

- The empty-profile baseline diagnostic is described in `diagnosing-bgs-problems` and is the most powerful single diagnostic primitive for modded BGS. This rule is its hygiene contract — without comparison validity, the baseline is noise.
- `install-planning.mod-update-post-state-discipline.v1` covers the intent-vs-effect distinction in mutation work; this rule covers the analogous trap in observation work.
- `archive-precedence.stale-ck-extract-loose-files.v1` is the specific case where this rule was learned.
