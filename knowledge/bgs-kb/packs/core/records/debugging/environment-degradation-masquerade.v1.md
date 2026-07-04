---
id: debugging.environment-degradation-masquerade.v1
title: Probabilistic environment degradation can masquerade as a code or record regression
kind: rule
domains: [debugging, engine]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Probabilistic UI, rendering, or machine-state failures can line up with a recent mod edit and look like deterministic causality. For random hard hangs with no CTD, no script error, silent logs, and reproduction across unrelated UI paths, reboot first and require repeated trials plus an all-related-changes-disabled control before blaming a record, script, or plugin edit.
  confidence: verified-project-doc
queryKeys:
  - probabilistic freeze
  - environment degradation
  - random hard hang
  - silent Papyrus log
  - reboot verification
  - UI renderer degradation
  - false attribution
  - Starview Analyzer
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 2026-07-04 extended Starview analyzer field test and reboot verification
    sectionPath: session prompt superseding E2E-FIELD-FINDINGS.md §9
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §9 Analyzer 卡死二号案结案 (historical conclusion superseded)
related:
  - papyrus.mesg-while-show-menu-loops.v1
  - papyrus.tutorial-state-machine-modal-collision.v1
  - debugging.asymmetric-evidence-self-falsify.v1
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# Probabilistic environment degradation can masquerade as a code or record regression

## Perspective: OBJECTIVE

When a symptom begins near a recent edit, the time line is seductive: edit A landed, symptom B appeared, therefore A caused B. That inference is only valid if the symptom is deterministic enough for the test design to carry attribution.

Probabilistic machine-state failures break that logic. Long-running Windows sessions, GPU or renderer degradation, input/UI stack decay, driver state, overlays, and game-runtime UI state can produce failures that appear and disappear across attempts. In that state, a single restore/retry pair can accidentally look like a perfect single-variable result.

## Diagnostic signature

Prefer the environment-degradation hypothesis when all or most of these are true:

- the failure is a hard hang or UI lock, not a normal CTD with a crash log;
- Papyrus logs are silent, or the last script lines do not explain the freeze;
- the failure is probabilistic rather than guaranteed;
- the symptom appears across unrelated UI routes, such as terminal-style activators, inventory exit, map opening, or other menus that do not share the suspected record/script path;
- disabling all related patches or data changes does not remove the symptom;
- a full computer reboot clears the symptom.

In that signature, the cheapest useful diagnostic step is a reboot. Do it before spending hours in xEdit or Papyrus attribution, unless the user is intentionally preserving the broken machine state for lower-level debugging.

## Attribution discipline for random hangs

For random or probabilistic failures, a single single-variable test has little attribution power. Require:

1. repeated trials of the suspected edit and its revert, enough to show the failure rate changes rather than one lucky outcome;
2. a control where all relevant mod data, patches, and script changes are disabled or restored, to prove the symptom is actually tied to the modded substrate;
3. a cheap environment reset such as game restart, MO2 restart, driver reset if applicable, and full computer reboot when UI/render state is suspected;
4. only then, record/script inspection for a deterministic cause.

If the clean control still reproduces the symptom, the suspected edit is not cleared or convicted by nearby timing. The failure class has changed: first diagnose the environment.

## Starview Analyzer case

In BB84's Starfield P10 Wave 2 field test, an early report blamed the second Starview Analyzer hard hang on a `MESG` `DESC` edit that reduced visible placeholders from five to three. The timing looked strong: edited text seemed to freeze, restored text seemed not to freeze.

Extended testing overturned that attribution:

- both local patches disabled, leaving pure original Starvival, still froze;
- the freeze was probabilistic, not guaranteed;
- unrelated UI re-entry paths could trigger it, including inventory exit and `Tab` to planet map;
- a computer reboot cleared all of it;
- after reboot, the five-to-three `DESC` edit could remain present without reproducing the hang.

The correct conclusion is not "placeholder structure can never matter." The correct conclusion is narrower and more useful: the hard-hang causality in that case was environment-level UI/render degradation, and the earlier perfect-looking edit/restore sequence was luck inside a random failure window.

The first Starview Analyzer hard-hang case remains different: the tutorial-modal attribution had timestamp-matched Papyrus traces and a post-fix control that passed. Do not collapse the two cases. One had script-level evidence; the second did not.

## Practical rule

When a UI hard hang is log-silent and crosses unrelated UI surfaces, run the reboot check early. If reboot cures it, record the episode as environment degradation and avoid sedimenting a false modding rule into the KB.

## See also

- `debugging.asymmetric-evidence-self-falsify.v1` covers comparison cleanliness for asymmetric observations.
- `papyrus.mesg-while-show-menu-loops.v1` covers the still-valid Papyrus menu-loop hygiene for `MESG.Show()` flows.
