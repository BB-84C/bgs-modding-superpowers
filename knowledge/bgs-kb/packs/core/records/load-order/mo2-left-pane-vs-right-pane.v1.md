---
id: load-order.mo2-left-pane-vs-right-pane.v1
title: MO2 left pane orders mod assets while the right pane orders plugins
domains: [load-order, archive-precedence, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: MO2's left-pane mod order controls deployed files and conflicts, while the right-pane plugin order controls record winners; fixing the wrong pane leaves the original symptom untouched.
  confidence: verified-tooling
queryKeys: [MO2 left pane, MO2 right pane, mod order, plugin order, conflict tab]
severity: critical
sources:
  - kind: tooling-docs
    url: "https://github.com/ModOrganizer2/modorganizer/wiki"
    ref: Mod Organizer 2 wiki
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: plugins.txt vs modlist.txt
related: [load-order.plugins-txt-vs-modlist.v1, archive-precedence.plugin-order-is-not-asset-order.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# MO2 left pane orders mod assets while the right pane orders plugins

In MO2, the left pane is the install/deployment layer: it decides which mod folder's loose files and generated outputs win file conflicts.
The right pane is the plugin layer: it decides `.esm`, `.esp`, and `.esl` order and activation.

A mesh, texture, script file, or generated behavior conflict is usually a left-pane or Overwrite issue.
A record override conflict is a right-pane load-order issue.
