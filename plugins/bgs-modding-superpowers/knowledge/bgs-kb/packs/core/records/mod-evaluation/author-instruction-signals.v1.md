---
id: mod-evaluation.author-instruction-signals.v1
title: Author instruction signals for safe mod installation
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Install interpretation starts from the author's own instructions: read requirements, variants, consequences, and file relationships before downloading or selecting installer options."
  confidence: high
queryKeys: [author instructions, author说明, install instructions, FOMOD choices, which file to download, variant selection, prerequisites, compatibility patches]
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 modpack tutorials (E2 前期准备, E11 MO2进阶, E12 整合搭建)
related: [mod-evaluation.quality-and-risk-signals.v1, mod-evaluation.community-operational-signals.v1]
lastReviewed: "2026-06-23"
schemaVersion: 1
---

# Author instruction signals for safe mod installation

Author说明 is the primary install surface. Before downloading or selecting options, read what the author says the mod requires, which files are current, which variants are mutually exclusive, how optional patches relate to the main file, and what consequences or uninstall warnings apply.

Prefer original pages or sources that preserve the author's explanation. Rehosts that carry only archives remove the context needed to interpret requirements and risk. If instructions are in another language, translate and understand them; language friction is not a reason to skip the install surface.

Treat missing instructions as a stop signal. Without enough explanation to understand requirements, variants, and consequences, a safe install plan cannot be formed.

Preserve traceability after installation. Name and classify main files, compatibility patches, translations, and optional components so future debugging can reconstruct ownership. Keep a path back to the original author page/source.

Use KB/game-specific records for runtime facts and operational hazards. This record gives the cross-game interpretation posture; it does not decide one game's current script-extender, archive, FOMOD, or plugin-limit rules.
