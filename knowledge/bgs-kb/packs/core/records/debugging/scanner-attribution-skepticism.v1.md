---
id: debugging.scanner-attribution-skepticism.v1
title: Auto crash-log scanner attribution is a lead, not a root-cause verdict
domains: [debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Auto crash-log scanners can mis-attribute a crash to an unrelated mod or file. Treat scanner output as a triage lead, then verify with the reproducible trigger, raw log context, recent-change window, and record/asset readback before removing or blaming a mod.
  confidence: curator-corpus
queryKeys: [crash scanner, crash log scanner, scanner attribution, auto scanner, misattribution, Buffout scanner, Trainwreck scanner]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/sixiang-build/evaluating-bgs-mods/framework-extraction.md
    sectionPath: Risk signals / Red flags
  - kind: project-internal-doc
    ref: .opencode/artifacts/sixiang-build/diagnosing-bgs-problems/framework-extraction.md
    sectionPath: Risk signals in the diagnosis itself
lastReviewed: "2026-06-23"
schemaVersion: 1
---

# Auto crash-log scanner attribution is a lead, not a root-cause verdict

Crash logs are evidence. Auto-scanner summaries are a weaker layer on top of that evidence.

BB84's diagnostic warning is that scanners can confidently blame an unrelated mod. The correct recovery is not to yank the named mod by ritual; it is to verify attribution:

1. reproduce the same crash route or action;
2. preserve the raw crash log and scanner output separately;
3. compare against the recent-change window;
4. inspect the concrete record, asset, native module, or loader state named by the evidence;
5. only then assign a root-cause class.

If the only evidence is "the scanner blamed X," the diagnostic state is still `NOT DIAGNOSED YET`.
