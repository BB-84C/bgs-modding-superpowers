---
id: xedit.runtime-ledger-partial-mutation-hazard.v1
title: A denied xEdit runtime symbol can abort after an earlier mutation
kind: gotcha
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: xEdit script failures are not transactional. Contract 0.23 preflights bare entry-script calls before Initialize, admits IntToStr64 and IntToHex/IntToHex64, and reports preExistingDirtyFiles plus mutationsAppliedBeforeFailure/modifiedFilesBeforeFailure. Helper-unit and dotted instance calls still rely on runtime policy, so inspect the structured failure fields and read the target back before retrying.
  confidence: verified-project-doc
queryKeys: [xEdit JvI ledger, policyPreflight, preExistingDirtyFiles, mutationsAppliedBeforeFailure, modifiedFilesBeforeFailure, IntToHex, IntToStr64, partial mutation]
severity: critical
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/29"
    ref: "Issue #29: xEdit runtime-ledger partial-mutation investigation"
    sectionPath: "3. Ledger gaps: IntToStr64 and IntToHex"
  - kind: github-issue
    url: "https://github.com/BB-84C/TES5Edit/issues/7"
    ref: "Upstream script-runtime hardening acceptance"
related:
  - xedit.scripts-constrained-runtime.v1
  - xedit.copy-into-deepcopy-for-structured-overrides.v1
  - xedit.mutations-require-iknowwhatimdoing.v1
lastReviewed: "2026-08-11"
schemaVersion: 1
---

# A denied xEdit runtime symbol can abort after an earlier mutation

The automation runtime has both compile-time and runtime policy boundaries. The
original incident left an orphan record when a formatting call was denied after
an earlier mutation. Contract 0.23 admits `IntToStr64`, two-argument Int64
`IntToHex`, and `IntToHex64`, and preflights bare entry-script call-shaped
identifiers before `Initialize`.

The preflight intentionally does not classify helper-unit symbols or dotted
instance methods; those remain runtime-hook responsibilities. Failures can report
`preExistingDirtyFiles`, `mutationsAppliedBeforeFailure`, and, when newly dirtied
files exist, `modifiedFilesBeforeFailure`. A false value means no newly dirty file
was observed, not proof that a pre-dirty file was untouched.

If any runtime error occurs after a mutation call, inspect those structured
fields and read the target file for the intended record and duplicates before
retrying. A failed response does not establish rollback.
