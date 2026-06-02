---
id: tooling-mo2.loot-user-metadata-rules.v1
title: LOOT user metadata records local sorting rules outside the plugin file
domains: [tooling.loot, load-order, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: LOOT metadata lets users express sorting constraints such as groups and plugin relationships without editing the plugin contents; user metadata should be preserved as part of the modlist's sorting policy.
  confidence: verified-tooling
queryKeys: [LOOT metadata, userlist.yaml, plugin groups, sorting rules, load after]
severity: high
sources:
  - kind: tooling-docs
    url: "https://loot.readthedocs.io/"
    ref: LOOT documentation
    sectionPath: Editing Plugin Metadata
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# LOOT user metadata records local sorting rules outside the plugin file

LOOT's sorting behavior is driven by metadata and graph constraints rather than by editing plugin headers.
User metadata is where local sorting policy belongs when a curated setup needs a rule not present in the shared masterlist.

Keep those rules with the modlist's operational state.
If LOOT repeatedly moves a plugin back, inspect metadata before hand-editing `plugins.txt` again.
