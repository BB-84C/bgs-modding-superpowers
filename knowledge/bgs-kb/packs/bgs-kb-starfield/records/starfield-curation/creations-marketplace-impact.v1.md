---
id: starfield-curation.creations-marketplace-impact.v1
title: Starfield Creations marketplace changes curation economics
kind: explanation
domains: [install-planning]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Starfield's Creations marketplace is a structural curation factor: it can carry important content outside the normal Nexus/MO2 patch ecosystem, so curators must decide whether local patching is acceptable for their pack."
  confidence: medium
queryKeys: [Starfield Creations marketplace, paid mods, Nexus patches, marketplace content]
severity: high
sources:
  - kind: official
    url: "https://store.steampowered.com/app/2722710/"
    ref: Starfield Creation Kit and Bethesda.net Creations sharing
  - kind: community-forum
    url: "https://www.nexusmods.com/site/news/14993"
    ref: Nexus Mods policy on paid mods, 2024-10-30
  - kind: tooling-docs
    url: "https://github.com/ModOrganizer2/modorganizer"
    ref: MO2 repository and Starfield game plugin visibility
  - kind: project-internal-doc
    ref: BB84 Q18 verbatim curator rationale
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield Creations marketplace changes curation economics

## Perspective: OBJECTIVE

Starfield is the first BGS game where the official Creations marketplace is not a side channel for curators; it is a primary distribution surface. That changes pack economics. Important content may be distributed through Bethesda.net rather than Nexus, while the dominant curator-class workflow still centers MO2, Nexus metadata, FOMOD installers, and local patch plugins.

The structural problem is the patch gap. Paid or Verified-Creator marketplace content can be unavailable for Nexus-side compatibility patch distribution under Nexus policy, and marketplace-managed files may not appear in MO2 with the same transparency as Nexus-installed mods. FOMOD-driven install choice also matters less for content shipped through the marketplace. The result is not simply "paid mods are bad"; it is that public patch distribution, dependency documentation, and reproducible pack assembly become harder.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

The plugin author's position is to include valuable Creations content when it fits the pack and solve compatibility locally: "在 Nexus 不能出 patch 不是阻碍的理由，因为我们现在做的这个 bgs modding superpowers 就是为了帮助玩家结合 AI Agent 搭建自己的整合包，构建本地的各种 patch". This is one curator/tool-author stance. Another curator may reasonably exclude marketplace content to preserve fully public, Nexus-reproducible patch flows.

Confidence downgrade: marketplace download-share and FOMOD-decline claims come from batch research findings, while the fetched Nexus news page did not expose the policy details in its extracted body.
