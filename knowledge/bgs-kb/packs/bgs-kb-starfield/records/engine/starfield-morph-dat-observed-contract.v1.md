---
id: engine.starfield-morph-dat-observed-contract.v1
title: Treat morph.dat as an observed Starfield asset contract, not a BodySlide constant table
kind: gotcha
domains: [engine, file-conflicts]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Vanilla Starfield apparel morph assets use morph.dat beneath the MRPH.TCMP folder, with an observed MDAT header and named chargen shape keys including Overweight, Thin, and Strong. Those names are observed Starfield asset conventions, not BodySlide constants; do not infer a complete writer contract or a morph.dat version field from this evidence.
  confidence: verified-project-doc
queryKeys: [Starfield morph.dat, MDAT, Overweight Thin Strong, chargen morph keys, MRPH TCMP]
severity: high
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/27"
    ref: "Issue #27: raw Starfield morph.dat inspection"
    sectionPath: "Part 3 — morph.dat container format and the canonical morph key names"
related:
  - plugin-format.starfield-apparel-chargen-morph-chain.v1
  - tooling.starfield-outfit-studio-headless-setup.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Treat Starfield morph.dat as an observed asset contract, not a BodySlide constant table

Vanilla Starfield examples inspected for the apparel chain place `morph.dat` under a path shaped like:

```text
meshes/morphs/<category>/<outfit>/<outfit>_<m|f>/chargen/<part>/morph.dat
```

The inspected bytes begin with `MDAT` and carry length-prefixed shape-key names. `Overweight`, `Thin`, and `Strong` were observed in vanilla Starfield assets. Preserve their spelling and case when comparing an asset with vanilla data.

This evidence deliberately does **not** define a `morph.dat` version field, a complete binary layout, validation rules, or a supported generation procedure. The three names are Starfield asset conventions observed in extracted game data; they are not asserted to be BodySlide or Outfit Studio constants. Likewise, this record does not claim that an automation XML or a generated file is accepted by the game.

`MWGT` remains a Fallout 4 comparison point, not a demonstrated Starfield equivalent. Keep generated-output and runtime-acceptance claims outside this record until they have separate asset and in-game readback.
