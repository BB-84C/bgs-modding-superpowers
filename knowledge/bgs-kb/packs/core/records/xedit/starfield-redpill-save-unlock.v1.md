---
id: xedit.starfield-redpill-save-unlock.v1
title: Starfield xEdit save gates require the RedPill switch trio for small, medium, and localized ESMs
kind: gotcha
domains: [xedit, plugin-format, debugging, version-differences]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Upstream xEdit 4.1.5k requires -ItJustWorksTM -ThisIsFine -GiveMeTheRedPill together to save Starfield small, medium, or localized ESMs. The BGS Modding Superpowers launcher passes the trio by default for Starfield sessions; opt out with xedit_start({ starfieldRedPill: false }) only when intentionally testing vanilla SF1 save gates. With RedPill on, the window title shows ItJustWorks[TM] Edition and files.create no longer auto-adds Starfield.esm as a master, so pass initialMasters=[\"Starfield.esm\"] or add required masters explicitly."
  confidence: verified-project-doc
queryKeys: [Starfield RedPill, GiveMeTheRedPill, ItJustWorksTM, ThisIsFine, Medium flagged files can't be saved in SF1Edit, small ESM save, localized ESM save, files.create initialMasters Starfield.esm]
severity: high
sources:
  - kind: official
    ref: xEdit 4.1.5k commit 1fcec21b3
    url: https://github.com/TES5Edit/TES5Edit/commit/1fcec21b3
    sectionPath: Starfield save gates / RedPill switches
  - kind: official
    ref: BB-84C/TES5Edit v4.1.6-automation.7 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.7
    sectionPath: automation.7 contract and launcher context
lastReviewed: "2026-07-06"
schemaVersion: 1
---

# Starfield xEdit save gates require the RedPill switch trio

Symptom: `session.save` fails for a Starfield small, medium, or localized ESM
with an error such as `save_failed: ... Medium flagged files can't be saved in
SF1Edit`.

Upstream xEdit 4.1.5k commit `1fcec21b3` added a three-switch unlock path for
Starfield save gates:

```text
-ItJustWorksTM -ThisIsFine -GiveMeTheRedPill
```

All three switches are required together. Passing them sets the RedPill path and
bypasses the SF1 gates for small/medium/localized ESM saving and the "Only full
modules can add masters" gate.

## BGS Modding Superpowers launcher behavior

The bundled launcher passes the trio by default for `gameMode: "Starfield"`
sessions. Opt out only when intentionally reproducing vanilla SF1 save-gate
behavior:

```text
xedit_start({ gameMode: "Starfield", starfieldRedPill: false })
```

## Side effects

- The xEdit window title changes to `ItJustWorks[TM] Edition`; this is a marker,
  not a containment breach.
- Under RedPill, `TwbFile.CreateNew` skips the auto-add of `Starfield.esm` as a
  master. Callers that need the base master must pass
  `files.create initialMasters=["Starfield.esm"]` or follow with
  `files.add_required_masters`.
