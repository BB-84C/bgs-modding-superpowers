---
id: xedit.runtime-ledger-partial-mutation-hazard.v1
title: A denied xEdit runtime symbol can abort after an earlier mutation
kind: gotcha
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: The xEdit automation JvI ledger can deny a Pascal helper at runtime after earlier statements have already mutated the plugin. Validate every required helper and move diagnostic formatting before record creation or copy operations; a later runtime-policy denial does not roll back an already-created record.
  confidence: verified-project-doc
queryKeys: [xEdit JvI ledger, IntToHex, IntToStr64, runtime policy denial, partial mutation, orphan record, AddMessage formatting]
severity: critical
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/29"
    ref: "Issue #29: xEdit runtime-ledger partial-mutation investigation"
    sectionPath: "3. Ledger gaps: IntToStr64 and IntToHex"
related:
  - xedit.scripts-constrained-runtime.v1
  - xedit.copy-into-deepcopy-for-structured-overrides.v1
  - xedit.mutations-require-iknowwhatimdoing.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# A denied xEdit runtime symbol can abort after an earlier mutation

The automation runtime has both compile-time and runtime policy boundaries. In the observed case, `IntToStr64` was undeclared at compile time, while `IntToHex` passed compilation but was denied by the JvI ledger at runtime. The second shape is more dangerous: a preceding `records.create` or `wbCopyElementToFile` had already succeeded, leaving an orphan record when the script stopped at a diagnostic log line.

Treat formatting and helper availability as a precondition, not cleanup. Keep a mutation script ordered as: validate inputs and helper availability, perform the minimally scoped mutation, then read back the created or copied record. Prefer existing summary/edit-value strings for diagnostics when integer-formatting helpers have not been verified in the active daemon ledger.

If any runtime error occurs after a mutation call, inspect the target file for the intended record and for duplicates before retrying. A failed response does not establish that the mutation rolled back.
