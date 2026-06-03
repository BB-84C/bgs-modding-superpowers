---
id: tooling-mo2.spriggit-plugin-serialization.v1
title: Spriggit serializes Bethesda plugins into reviewable text for Git workflows
domains: [tooling.spriggit, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Spriggit turns Bethesda plugin content into a text representation intended for version control, reviews, branches, and collaborative mod development.
  confidence: verified-tooling
queryKeys: [Spriggit, plugin serialization, git modding, YAML, text records]
severity: medium
sources:
  - kind: tooling-docs
    url: "https://mutagen-modding.github.io/Spriggit/"
    ref: Spriggit documentation
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Spriggit serializes Bethesda plugins into reviewable text for Git workflows

Spriggit is for source-control workflows around plugin data.
Instead of treating a binary plugin as an opaque blob, teams can review and merge textual output in Git-like collaboration.

The serialized files are still an intermediate representation of game plugin data, not a license to ignore game-specific release settings.
Round-trip claims should be tested on the target game and plugin before a modpack relies on them.
