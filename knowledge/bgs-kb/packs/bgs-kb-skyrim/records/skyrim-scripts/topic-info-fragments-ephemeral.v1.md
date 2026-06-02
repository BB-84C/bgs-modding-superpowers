---
id: skyrim-scripts.topic-info-fragments-ephemeral.v1
title: Skyrim topic-info fragments are transient dialogue scripts
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Topic Info fragments run at dialogue start/end and CK warns not to hold properties or variables pointing at those fragment scripts because they do not persist like normal script objects."
  confidence: verified-tooling
queryKeys: [Topic Info Fragment, dialogue fragment, TIF, transient script]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki Topic Info Fragments
    url: https://ck.uesp.net/wiki/Topic_Info_Fragments
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim topic-info fragments are transient dialogue scripts

Topic Info fragments are generated around dialogue topics and run when the topic begins or ends.
They are not a good place to anchor long-lived state.

The CK page warns that holding properties or variables pointing at a topic-info fragment script can produce odd behavior.
Put durable state on a quest, alias, or explicit script object instead.

Use this when a dialogue fragment appears to work once but loses state later.
