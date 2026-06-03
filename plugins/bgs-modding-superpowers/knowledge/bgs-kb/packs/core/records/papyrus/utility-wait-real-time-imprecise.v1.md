---
id: papyrus.utility-wait-real-time-imprecise.v1
title: Utility.Wait is latent real-time delay and not frame-precise
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Utility.Wait pauses the current Papyrus stack for at least a real-time interval, but CK notes that wait duration is not precise and depends on frame rate and Papyrus workload.
  confidence: verified-tooling
queryKeys: [Utility.Wait, latent wait, real time, imprecise wait, menu mode]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki Wait - Utility
    url: https://ck.uesp.net/wiki/Wait_-_Utility
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Utility.Wait is latent real-time delay and not frame-precise

`Utility.Wait` is a latent wait on the current script stack.
It waits real-world time and does not count ordinary menu-paused time.

The CK notes explicitly warn that wait timing is affected by frame rate and general Papyrus workload.
That makes it unsuitable for exact sequencing or tight polling loops.

Use events or update registration when ordering matters more than a rough delay.
