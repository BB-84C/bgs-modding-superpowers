---
id: papyrus.tutorial-state-machine-modal-collision.v1
title: Tutorial state-machine auto-advance can deadlock against modal message queues
kind: gotcha
domains: [papyrus, debugging]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "When patching a tutorial or guide state machine to auto-advance on load, audit every modal Show() and ShowAsHelpMessage() on the new path. If load-time auto-advance reaches modal prompts while another menu loop is open, the modal queue can deadlock; the safer patch shape is silent completion: skip all modal displays, set all completion flags together, restore any world state the tutorial disabled, and prevent re-entry."
  confidence: verified-project-doc
queryKeys: [Papyrus tutorial auto-advance, modal Show deadlock, ShowAsHelpMessage, silent complete, tutorial state machine]
severity: critical
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §8 Analyzer 卡死事件结案
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-a/LANE-A-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.8 紧急修复 — 教程 auto-advance 静默完成
related: [papyrus.states-dispatch-by-current-state.v1, papyrus.properties-are-save-state.v1, papyrus.mesg-while-show-menu-loops.v1]
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# Tutorial state-machine auto-advance can deadlock against modal message queues

Tutorial state machines often combine saved booleans, quest globals, timers, player controls, and modal messages. Patching one step to auto-advance is not enough: a save may already contain an in-progress tutorial state, and load-time rescue code can push the script through later modal prompts immediately.

Audit the full reachable chain after the new auto-advance point. For every step, identify whether it calls `Show()` or `ShowAsHelpMessage()`, whether it changes world state such as takeoff or fast-travel enablement, and which flags prevent the branch from re-entering on the next tick or load.

When the patch goal is to retire the tutorial path, prefer silent completion:

1. Skip every modal display on the auto-advance path.
2. Set all completion booleans and globals in one pass.
3. Restore world state that the tutorial may have disabled, such as `EnableTakeoff(True)`.
4. Cancel or finish the timer driving the tutorial.
5. Add trace lines at each suppressed modal and at the final completion point.

Reference case: a Starvival fuel tutorial rescue advanced on save load while the Starview Analyzer menu's `While Show` loop was open. Three sessions froze at timestamps matching the auto-advance traces. The fix suppressed eleven tutorial modal messages, set all completion flags/globals, re-enabled takeoff, and made the branch non-reentrant.
