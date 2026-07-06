---
id: install-planning.partial-disable-requires-author-toggle.v1
title: Partial-disable patches require a real author-exposed toggle or deep subsystem surgery
kind: rule
domains: [install-planning, papyrus]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: A BGS mod sub-feature can be safely partial-disabled only when the author exposed an independent toggle in settings, a config menu, a holotape/book, records, or scripts; otherwise the patch becomes high-risk Papyrus and quest-entry surgery, not a surface GLOB or OMOD workaround.
  confidence: verified-project-doc
queryKeys: [partial disable, subsystem toggle, Configuration Book, papyrus sub-feature, mod patching]
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 Lane 3 audit synthesis
    sectionPath: partial-disable toggle discipline
related: [mod-evaluation.systemic-design-fit.v1]
lastReviewed: "2026-06-29"
schemaVersion: 1
---

# Partial-disable patches require a real author-exposed toggle or deep subsystem surgery

Do not treat partial-disable requests as cosmetic load-order work. If the author already exposed a real independent switch, prefer the low-intrusion path: override the default setting or controlling record and verify the disabled subsystem actually honors it.

If no such switch exists, assume the underlying Papyrus and quest graph has no sub-feature toggle interface. A safe patch then requires finding the subsystem's true entry points, such as startup quests, script events, aliases, active effects, or configuration globals that are actually read by code. The patch must block that subsystem without breaking adjacent systems that share state or callbacks.

This is a high-complexity task because inter-system contracts may be implicit. Disabling one quest, event listener, or reward path can strand state expected by another subsystem.

Do not propose `OMOD` as a generic solution. OMOD records are object modification data, typically for weapon or armor modifications, and do not disable arbitrary mod subsystems.

Reference case: Starvival does not expose independent fuel/O2/wage toggles, so splitting those systems is a difficult Papyrus and quest architecture patch rather than a simple configuration override.
