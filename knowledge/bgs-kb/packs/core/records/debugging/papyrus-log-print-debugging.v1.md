---
id: debugging.papyrus-log-print-debugging.v1
title: Prefix-rich Papyrus Debug.Trace instrumentation turns runtime bugs into time-aligned evidence
kind: workflow
domains: [debugging, papyrus]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: For Papyrus patch campaigns, add stable Debug.Trace prefixes plus key state values at entries, skipped payloads, timer re-arms, and global/property writes. This turns field reports from guesswork into timestamp-aligned evidence; compile without stripping debug traces, and compare the bug time to the trace sequence before changing the patch again.
  confidence: verified-project-doc
queryKeys: [Papyrus Debug.Trace instrumentation, log prefix, state values, timer rearm, payload skipped, Papyrus log]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §1 三线核心判定; §8 Analyzer 卡死事件结案
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-a/LANE-A-CONSTRUCTION-REPORT.md
    sectionPath: Debug.Trace 插桩; Wave 2.8 紧急修复
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-b/LANE-B-CONSTRUCTION-REPORT.md
    sectionPath: Debug.Trace 插桩点清单
related: [papyrus.debug-trace-logging-ini.v1, papyrus.debug-notification-is-ui-not-log.v1]
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# Prefix-rich Papyrus Debug.Trace instrumentation turns runtime bugs into time-aligned evidence

When a Papyrus patch changes state-machine or timer behavior, logging is not optional polish. A stable trace prefix plus state values lets the curator align the exact in-game freeze, prompt, or state change with the script path that just executed.

Instrumentation should include:

- function and event entry points, with the controlling state values;
- every payload skip introduced by the patch, with enough context to prove the skipped behavior was the intended subsystem;
- timer re-arm and cancel points, especially when sibling systems share a timer;
- global, property, or actor-value writes, recording before and after values when possible;
- null-guard and missing-form paths with a higher severity level.

Keep prefixes stable and grep-friendly, such as `[BB84_P10A]`, `[BB84_P10B]`, or a mod/package identifier. Do not compile with flags that strip trace evidence when runtime readback is still required.

Reference case: P10's fuel patch used trace lines for payload skips, maintenance timer re-arm, and tutorial modal suppression. Three independent field sessions froze within seconds of the same tutorial auto-advance trace sequence, which localized the bug to the tutorial chain rather than to the visible menu message records.
