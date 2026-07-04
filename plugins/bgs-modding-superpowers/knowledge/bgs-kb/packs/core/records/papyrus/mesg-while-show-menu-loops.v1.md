---
id: papyrus.mesg-while-show-menu-loops.v1
title: MESG-driven While Show menu loops need balanced routing and -1 back-out handling
kind: rule
domains: [papyrus, plugin-format, debugging]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: A Papyrus menu loop built around MESG.Show() must handle the button value returned by Show(), including -1 back-out/failure paths, and every MenuType route must have a matching Show call or terminal handler. Empty -1 branches, orphan MenuType assignments, removed Show calls, or DESC edits that change placeholder count/structure can create silent engine-side hangs; MESG BNAM, button layout, and format placeholders are behavioral data, not just text.
  confidence: verified-project-doc
queryKeys: [MESG Show, While menu loop, Button -1, BNAM, MenuType, Starview Analyzer, DESC placeholder, engine hang]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §8-§9 Analyzer 卡死事件结案 / 二号案结案
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-a/LANE-A-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.6 修补 — 残留交互面清理
related: [papyrus.tutorial-state-machine-modal-collision.v1]
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
- `DESC` placeholder count and structure are behavior-surface data for script-driven `Show()` messages. Do not delete a sentence that carries placeholders or reduce the number of placeholders just because the script passes more arguments than the edited text appears to need.
- Safe copy edits keep the same placeholder arity and ordering, changing only the surrounding words between placeholders. Placeholder-removing edits are high risk and need a single-variable in-game test before they can be trusted.

Reference case: Starvival's Starview Analyzer used a `While MenuOpened` + `MSG.Show()` menu tree. The patch kept the honest fuel readout but redirected fuel-management buttons back to the main menu, removed actor-value registration, and verified there were no orphan routes or missing `Show()` calls in the modified paths.

Follow-up field result: `_SISA_Message_Spaceship_Starview_Main_Information_Capacity` (`MESG:31000BC3`) was displayed by script `Show()` from that menu. Removing a rate line reduced the `DESC` placeholders from five to three. BB84 tested the edit as a single variable twice: edited text produced a hard analyzer freeze on exit; restoring the original text removed the freeze. Papyrus emitted no error and no defensive `-1` trace, and the message records had no button/BNAM, localized-strings, or other structural differences. Other simultaneous plugin changes, including LVLI injection and a new master, remained present in a non-freezing build and were excluded.

Diagnostic signature: engine hard hang plus silent Papyrus logs after a script `Show()` message edit points at engine-side message formatting or modal handling, not a script-layer branch bug. Do not keep digging in Papyrus just because the script has a nearby loop.

Debugging lesson: in a multi-source freeze, "revert A and the freeze still happens" does not clear A. It only proves at least one other freeze source remains. Attribution requires a single-variable test after the competing source is removed; the Starview case first mis-cleared the `MESG:31000BC3` edit because an independent tutorial-modal hang was still present.
