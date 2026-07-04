---
id: papyrus.mesg-while-show-menu-loops.v1
title: MESG-driven While Show menu loops need balanced routing and -1 back-out handling
kind: rule
domains: [papyrus, plugin-format, debugging]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: A Papyrus menu loop built around MESG.Show() must handle the button value returned by Show(), including -1 back-out/failure paths, and every MenuType route must have a matching Show call or terminal handler. Empty -1 branches, orphan MenuType assignments, or removed Show calls can create silent infinite loops; MESG BNAM, button layout, DESC placeholders, and line-break encoding are behavioral data, not just text.
  confidence: verified-project-doc
queryKeys: [MESG Show, While menu loop, Button -1, BNAM, MenuType, Starview Analyzer, DESC placeholder, CRLF, line break]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §8-§9 Analyzer 卡死事件结案 / 二号案结案; §9 causality superseded by 2026-07-04 reboot verification
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-a/LANE-A-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.6 修补 — 残留交互面清理
related: [papyrus.tutorial-state-machine-modal-collision.v1, debugging.environment-degradation-masquerade.v1]
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# MESG-driven While Show menu loops need balanced routing and -1 back-out handling

Papyrus UI flows often implement menus as a `While` loop around `MESG.Show()`, with a `Button` return value and a separate `MenuType` or state variable deciding the next screen. That structure is fragile under partial-disable patches because removing one action can unbalance the loop.

Treat these as behavior, not text:

- The returned `Button` value drives control flow. A `Button == -1` branch is the back-out or failed-show path; leaving it empty can spin the loop forever if a message fails to show or the user backs out.
- Every `MenuType = X` assignment must have a matching route that either displays the intended message, redirects deliberately, or exits the loop.
- Removing a `Show()` call without changing the route can produce an orphan loop iteration with no user-visible prompt.
- `MESG` `BNAM` back-out index and button count are behavior-surface fields. Copying only the text while changing button structure can change script return values.
- `DESC` placeholder count and structure are behavior-surface data for script-driven `Show()` messages. The conservative edit shape is to keep placeholder arity and ordering, changing only the surrounding words between placeholders.
- That placeholder rule is a safe-editing habit, not a proved hard-hang cause. A prior Starview Analyzer field note that blamed a five-to-three placeholder edit for a hard hang was later overturned by broader controls and reboot verification; see `debugging.environment-degradation-masquerade.v1`.
- `DESC` line-break encoding matters. When matching original multi-line message text, preserve `CRLF` (`\r\n`) structure; a bare carriage return (`\r`) can display abnormally.

Reference case: Starvival's Starview Analyzer used a `While MenuOpened` + `MSG.Show()` menu tree. The patch kept the honest fuel readout but redirected fuel-management buttons back to the main menu, removed actor-value registration, and verified there were no orphan routes or missing `Show()` calls in the modified paths.

Correction to the follow-up field result: `_SISA_Message_Spaceship_Starview_Main_Information_Capacity` (`MESG:31000BC3`) was displayed by script `Show()` from that menu, and one edit reduced the visible `DESC` placeholders from five to three. The first field pass correlated that edit with a hard analyzer freeze. Later controls overturned that causal assignment: pure original Starvival with both local patches disabled still froze; the symptom was probabilistic; it appeared across unrelated UI re-entry paths such as the terminal-style analyzer activator, inventory exit, and even `Tab` to planet map; and a computer reboot cleared the whole symptom, including with the five-to-three placeholder edit still present.

Diagnostic implication: a UI hard hang with no CTD, no Papyrus error, silent logs, and cross-UI-path reproduction is not enough to blame the nearest `MESG` or Papyrus loop. Treat environment-level UI/render degradation as a live hypothesis and reboot before deep record-level attribution.

What still stands from this record: MESG-driven menu loops still need balanced button routing, `-1` handling, and route cleanup. For text-only edits, keep placeholders and line breaks structurally conservative, then verify repeated behavior. Do not convert a probabilistic UI failure into a deterministic data-cause verdict from one lucky restore/retry pair.
