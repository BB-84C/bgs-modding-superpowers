---
id: tooling-mo2.mo2-visible-start-required.v1
title: MO2 must be started visibly so the control-plane plugin can load and be observed
domains: [debugging, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The setup workflow starts MO2 as a visible GUI process, not hidden or background-only, so the control-plane plugin can load and the operator can observe or resolve blockers.
  confidence: verified-project-doc
queryKeys: [visible MO2, start-mo2.ps1, zombie MO2, control plane plugin]
severity: high
sources:
  - kind: project-skill
    ref: skills/setting-up-bgs-modding-environment/SKILL.md
    sectionPath: Start MO2 visibly
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# MO2 must be started visibly so the control-plane plugin can load and be observed

Visible MO2 is an operational invariant for this plugin.
The user or operator must be able to see the GUI, and the control-plane plugin must have a real MO2 process to attach to.

Hidden launches and zombie processes create ambiguous failures where the shell is alive but the harness is not usable.
The setup skill's launch helper detects those states and reports them.

Agents should not try to make MO2 invisible just to make automation look cleaner.
