---
id: install-planning.numeric-fetish-anti-signal.v1
title: Marketing a pack by mod count or disk size is a curation anti-signal
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "When a modpack's primary marketing is mod count or disk size, treat that as a marketing-not-curation anti-signal; pack quality measures in coherence, not count."
  confidence: high
queryKeys: [mod count, disk size, curation anti-signal, modpack quality, pack coherence, 无脑]
severity: medium
sources:
  - kind: project-internal-doc
    ref: "BB84 corpus Q16 verbatim point 1, the 无脑 anti-patterns"
  - kind: community-forum
    url: "https://www.reddit.com/r/skyrimmods/wiki/begin2/"
    ref: "r/skyrimmods beginner guidance"
  - kind: community-forum
    url: "https://www.reddit.com/r/FalloutMods/wiki/moderation/mods_modding/"
    ref: "r/FalloutMods modding resources wiki"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Marketing a pack by mod count or disk size is a curation anti-signal

Raw mod count and disk size are poor quality metrics. A pack advertised first as "4000 mods" or "2TB" is usually selling scale as spectacle, not explaining what world it creates. The objective problem is not taste; it is risk geometry. Every added mod can conflict with every existing mod at the file layer, plugin-record layer, Papyrus/runtime layer, archive layer, and UI/localization layer. In the worst case, conflict surface grows roughly with pair count, while validation time grows even faster because interactions are behavioral, not just structural.

BB84 Q16 point 1 is cited here as the compact warning from the corpus: "无脑" count-chasing is an anti-pattern. That quote should not be read as "large packs are always bad." Large packs can be excellent when they show patch strategy, testing rhythm, rollback planning, conflict ownership, and a clear style target. The anti-signal is when the headline number replaces those explanations.

Curators should ask what the number is doing. If count appears alongside named layers, compatibility patches, conflict rules, and known limitations, it is just inventory. If count is the main promise, expect the author to be optimizing for download volume, video clicks, or novelty. A carefully patched 200-mod pack can outperform a 4000-mod pile because coherence is the product.

Use this rule during evaluation and installation planning. Do not reject purely because the number is high; instead require stronger evidence proportional to scale: maintained patches, reproducible install order, known conflict resolution, and proof that the author has played the resulting world long enough to catch silent failures.
