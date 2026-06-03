---
id: load-order.mod-enabled-and-plugin-active-are-orthogonal.v1
title: MO2 mod enablement and plugin activation are orthogonal checks
domains: [load-order, install-planning, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A plugin can only load when the containing MO2 mod is enabled and the plugin activation surface also marks it active; checking only one surface can produce false conclusions.
  confidence: verified-project-doc
queryKeys: [plugin not loading, mod enabled, plugin active, MO2 checkbox, modlist.txt]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: plugins.txt vs modlist.txt
related: [load-order.plugins-txt-vs-modlist.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# MO2 mod enablement and plugin activation are orthogonal checks

MO2 has two relevant toggles: the mod folder can be enabled or disabled, and the plugin file can be active or inactive.
An enabled mod folder may still contain an inactive plugin; an active plugin entry may fail if its providing mod is disabled or missing.

For “plugin missing” diagnostics, inspect both `modlist.txt` and the load-order surface.
Do not interpret the `+` or `-` modlist prefix as plugin activation.
