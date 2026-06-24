---
id: mod-evaluation.author-signals.v1
title: "Author maintenance signals: objective risk cues plus BB84's weighting"
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Author behavior is operational evidence: public changelogs, bug engagement, known-issues disclosure, and patch-friendly permissions reduce risk; deleted criticism, paywalled essentials, plagiarism, contradictions, and serial abandonment raise it."
  confidence: high
queryKeys: [author signals, mod author, changelog, bug reports, Patreon locked, plagiarism, permissions, known issues, community patches]
severity: high
sources:
  - kind: official
    url: "https://help.nexusmods.com/article/28-file-submission-guidelines"
    ref: Nexus Mods file-submission and asset-permission rules
  - kind: community-forum
    url: "https://www.reddit.com/r/skyrimmods/wiki/begin2/"
    ref: r/skyrimmods beginner guidance on reading mod pages, comments, requirements, and bugs
  - kind: project-internal-doc
    ref: BB84 corpus — Q7/Q8 verbatim curator answers
related: [mod-evaluation.author-instruction-signals.v1, mod-evaluation.community-operational-signals.v1, mod-evaluation.bb84-curator-perspective-reference.v1]
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Author maintenance signals: objective risk cues plus BB84's weighting

## Perspective: OBJECTIVE

Treat author behavior as operational evidence, not personality judgment. The safest authors make their mod's current state legible: clear changelog, current requirements, version notes, known issues, compatibility caveats, and bug-report responses that distinguish user error from real defects. They leave enough public information for a curator to predict install shape and future maintenance cost.

Objective red flags include deleting critical comments instead of answering them; locking the main version or essential compatibility patches behind Patreon or another paywall; plagiarism or unauthorized assets; requirements that contradict each other; hidden dependencies discovered only after install; and a pattern of abandoning a broken mod, then shipping a new replacement under the same unresolved maintenance posture.

Objective green flags include a dated changelog, visible response to reproducible bug reports, a public known-issues section, explicit version compatibility, open permissions where legally possible, and encouragement of community patches or forks when the author cannot maintain every integration. A terse page is not automatically unsafe, and a polished page is not automatically safe; the question is whether the author leaves enough traceable evidence for curation.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84 weights author signals heavily because a modpack is a long-running maintenance relationship. His top three green flags are: multiple high-quality works under the same account, visible responsiveness to bug reports, and a clear changelog that makes version migration understandable. These signals tell him the author is likely to keep producing patchable, explainable work rather than isolated upload spikes.

His hard red line is a Patreon-locked main version or essential patch. Optional early-access builds are one thing; putting the functional public version or necessary compatibility layer behind a paywall breaks the community patch ecosystem he relies on. Other curators may choose differently, especially for private packs, but BB84 treats paywalled essentials as a reject signal.

This subjective weighting does not replace the objective checks. If the author is quiet but the mod is stable, transparent, and narrow in scope, it may still be acceptable. If the author is charismatic but the page hides risks, the risk remains.
