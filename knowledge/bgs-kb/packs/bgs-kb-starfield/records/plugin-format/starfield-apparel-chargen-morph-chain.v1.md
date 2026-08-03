---
id: plugin-format.starfield-apparel-chargen-morph-chain.v1
title: Apparel chargen morphs link through Starfield ARMA and MRPH records
kind: explanation
domains: [plugin-format, engine]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Starfield apparel body morphing is an asset-and-record chain: ARMO models lead to ARMA, ARMA.NAM4/NAM6 point to top-level MRPH records, and MRPH.TCMP names the folder containing morph.dat. A garment without the ARMA-to-MRPH links has no demonstrated binding to the chargen body morphs, so load-order changes alone cannot supply missing mesh deformation data."
  confidence: verified-project-doc
queryKeys: [Starfield apparel morph chain, ARMA NAM4 NAM6, MRPH TCMP, morph.dat folder, chargen clothing clipping]
severity: high
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/27"
    ref: "Issue #27: verified Starfield apparel body-morph investigation"
    sectionPath: "Part 2 — The Starfield apparel body-morph chain"
related:
  - engine.starfield-morph-dat-observed-contract.v1
  - plugin-format.starfield-crowd-apparel-equip-pipeline.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Starfield apparel chargen morphs link through ARMA and MRPH records

The observed Starfield chain is:

```text
ARMO models -> ARMA.NAM4 / ARMA.NAM6 -> MRPH -> MRPH.TCMP -> <folder>/morph.dat
```

`NAM4` is the male world-morph link and `NAM6` is the female world-morph link in the inspected equippable apparel. `MRPH` is a top-level record signature in xEdit, not a `MOPRH` subrecord on `ARMA`. Its `TCMP` value names a folder; the observed file convention inside that folder is `morph.dat`.

The investigated crowd `ARMA` had neither `NAM4` nor `NAM6`. That explains the observed result in which the actor body followed chargen sliders while the garment did not: record or load-order changes cannot create the absent morph asset and its vertex deltas.

Before designing a wearable conversion, inspect the source `ARMA` links and compare them with a known-good garment of the same body region. This record describes the observed linkage and is not a claim that a generated morph file will be accepted by the game.
