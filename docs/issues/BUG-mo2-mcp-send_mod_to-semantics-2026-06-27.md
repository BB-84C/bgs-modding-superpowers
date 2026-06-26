# BUG: mo2-mcp `send_mod_to` semantics on cross-separator moves don't match docs / curator expectations

> ## [RESOLVED / SUPERSEDED 2026-06-27 — DO NOT USE THIS REPRODUCER AS-IS]
>
> This bug was filed by orchestrator-delta during BB84 Starfield Lane 3 Phase A on 2026-06-27 based on **inverted modlist readout semantics**. The reproducer "expectations" listed below assumed the wrong priority-direction convention (I thought higher priority = top of GUI = wins; actually higher priority = bottom of GUI = wins, which is mobase's standard convention).
>
> Resolved by three PRs that landed the same day:
> - **PR #17** (`7ffa693`) — `send_mod_to uses full priority space, reverts nonSepRank`
> - **PR #18** (`63c4f6c`) — `GUI-aligned vocabulary for send_mod_to + create_mod + create_separator` + read-side enrichment (now exposes `_meta.array_order=gui_top_first`, `priority_convention=mobase_full_space_higher_wins`, `section_rule`, plus per-mod `section` and `gui_rank` fields)
> - **PR #19** (`2c3a068`) — `auto-call organizer.refresh() after all mutating handlers`
>
> Empirical verification (2026-06-27, post-fix):
> - Modlist response now includes `_meta` block explicitly stating direction contract
> - Each mod has explicit `section` field
> - Each plugin has `gui_rank` + `load_order_role` (intermediate / loads_first_lowest_precedence / loads_last_highest_precedence)
> - BB84's manual move of rbt_suitup_creations-cc verified correct: at priority 406 with `section: 版本已过期_separator` exactly as intended
>
> The orchestrator's reproducer steps below show what HAPPENED, but the "expected" annotations are wrong because they assumed inverted semantics. Keep this file as historical record of the inversion-misread incident. Future curator-side semantic confusion should reference the new `_meta` contract instead of relitigating this issue.

---

**Filed**: 2026-06-27
**Reporter**: orchestrator-delta during BB84 Starfield Lane 3 Phase A
**Severity**: ~~Medium~~ — **misread by reporter; closed via PRs #17/#18/#19**
**Affected tool**: `Mo2Mo2SendModTo_tool` (`mo2_send_mod_to` broker call)
**Workaround**: ~~manually drag in MO2 GUI~~ — **no longer needed post-PR-18**

## Summary

Two distinct unexpected behaviors observed in a single session:

1. **`above_separator` interpretation contradicts visual semantics**: targeting a separator by name with `above_separator` mode placed the mod in an area BELOW the named separator visually (i.e., at a LOWER priority number than the separator), not above.
2. **`priority` mode rejects priorities past adjacent separator boundary**: explicit `priority: N` with N past the nearest separator above the mod's current position returned `priority N out of [0..(separator_priority - 1)]`. Suggests broker treats mod priority as bounded by the section it currently belongs to.

Combined effect: **cannot programmatically move a mod across separator boundaries** without iterative section-by-section repositioning (still unverified if even that works).

## Environment

- MO2 instance: `D:\Starfield MO2`
- Profile: `BB84自用2` (Chinese name, UTF-8 / `@ByteArray(\xHH)`-encoded)
- MO2 state: running (broker connected, sidecar ready)
- Permission ceiling: `full-control`
- mo2-mcp version: current main (post PR #15 merge, fe28683 / f551c56)
- Total mods in profile: 407 (including separators)

## Concrete reproducer (snapshot of session 2026-06-27)

### Initial state

- `rbt_suitup_creations-cc` enabled, priority 149, in separator `沉浸感增强 - 音效` area (priority 150)
- Target: move to `版本已过期_separator` group (priorities 379-394, between separator at 395 and the next separator below at 378)

### Step 1 — disable mod (worked)

```
Mo2Mo2ToggleMod_tool(mode=plan, name="rbt_suitup_creations-cc", enabled=false, profile="BB84自用2")
→ plan_id, lease_token, diff "rbt_suitup_creations-cc: + → -"
Mo2Mo2ToggleMod_tool(mode=apply, ..., plan_id, lease_token)
→ ok, applied
```

Mod disabled successfully, priority stayed at 149.

### Step 2 — try `above_separator: 观望_separator` (UNEXPECTED)

```
Mo2Mo2SendModTo_tool(
  mode=plan, name="rbt_suitup_creations-cc",
  target_mode="above_separator",
  target_separator="观望_separator",
  profile="BB84自用2"
)
→ diff: "rbt_suitup_creations-cc: → priority 349 (mode=above_separator)"
```

**Expected**: priority just above 观望_separator (which is at priority 378), so placement at ~377 or somewhere INSIDE the 版本已过期 group above 观望.

**Actual**: priority 349 — which is FAR BELOW 观望_separator (378) visually. Priority 349 is in the "My Mods / Other Mods" area, well past several intermediate separators (`Test Mods_separator` at 373, `等待作者更新_separator` at 367, `My Mods_separator` at 346).

### Step 3 — try explicit `priority: 379` (REJECTED)

```
Mo2Mo2SendModTo_tool(
  mode=plan, name="rbt_suitup_creations-cc",
  target_mode="priority", target_priority=379,
  profile="BB84自用2"
)
→ plan succeeded with diff "rbt_suitup_creations-cc: → priority 379 (mode=priority)"
Mo2Mo2SendModTo_tool(mode=apply, ..., target_priority=379, plan_id, lease_token)
→ ERROR: { code: "internal_error", message: "priority 379 out of [0..377]" }
```

**Expected**: mod relocated to priority 379 (at the bottom of 版本已过期 group, right above Revelation - Main Quest Temple Overhaul which currently holds priority 379).

**Actual**: rejected with "out of [0..377]". The cap of 377 corresponds exactly to `观望_separator priority (378) - 1`. Suggests broker bounded the mod's valid priority range to the section currently containing it.

### Step 4 — try `above_separator: 版本已过期_separator` (UNEXPECTED)

```
Mo2Mo2SendModTo_tool(
  mode=plan, name="rbt_suitup_creations-cc",
  target_mode="above_separator",
  target_separator="版本已过期_separator",
  profile="BB84自用2"
)
→ diff: "rbt_suitup_creations-cc: → priority 365 (mode=above_separator)"
```

**Expected**: priority just above 版本已过期_separator (which is at priority 395), so placement at ~394 (top of the 版本已过期 group).

**Actual**: priority 365 — inside `等待作者更新` section (between `等待作者更新_separator` at 367 and `Test Mods_separator` at 373).

### Step 5 — applied (anyway, to release lease)

After applying the priority 365 placement, the mod ended up in the `等待作者更新` area which is semantically WRONG (the mod is superseded, not waiting for update). Curator BB84 then manually moved it to the correct location in MO2 GUI.

## Hypothesis matrix

| Hypothesis | Evidence for | Evidence against |
|---|---|---|
| **A**: `above_separator` semantic is "place inside the section that ends at the named separator", but the section identification is off by N separators | The pattern: targeting `观望` (378) placed in My Mods area; targeting `版本已过期` (395) placed in 等待作者更新 area. Each placement is ~2-3 separators below the named target. | Unclear why "off by N". |
| **B**: priority semantics in broker are INVERTED relative to MO2 GUI visual order | "above" semantically = "below visually" would explain step 2 and 4 — but inconsistently (step 2 missed by more sections than step 4) | If pure inversion, priority 394 should also be rejected from priority-mode call with same out-of-range. Both should be symmetric. |
| **C**: broker treats current section as the only addressable range; cross-section moves not supported via priority mode | Step 3 error message "out of [0..377]" matches the next separator above the mod's current position. | Doesn't explain why `above_separator` produced a target priority OUTSIDE the current section without error. |
| **D**: broker has a bug in separator-relative position calculation specific to certain modlist layouts (Chinese separator names? UTF-8 `@ByteArray` paths?) | BB84's profile uses Chinese separator names and `@ByteArray` encoding (recent bugfix area). | BB84 manually-moved successfully via GUI; profile name encoding didn't block disable + meta.ini edits. Possible but not strongly supported. |

Most likely: combination of A + C. Broker may have an off-by-N section identification bug AND a section-boundary clamp on priority mode that prevents cross-section moves entirely.

## Suggested investigation steps

1. **Bisect the off-by-N**: try `above_separator` with each separator in BB84's modlist, log the resulting placement priority. Plot delta. If consistent N, it's a clear arithmetic bug.
2. **Check synthetic modlist**: reproduce with ASCII-only separator names in a fresh test profile. If the issue disappears, it's a Chinese/encoding-path bug. If it persists, it's a generic broker semantic issue.
3. **Read `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` handler for `mods.send_mod_to`** (or equivalent): inspect the priority-mode bounds calculation AND the above_separator destination-priority computation. Both diverge from documented behavior.
4. **Verify against MO2 source**: MO2's `IModList.setPriority` semantics are documented in modorganizer/include/ipluginlist.h. Compare what the broker computes vs what `IModList::setPriority` would accept.
5. **Acceptance regression**: add a fixture-based test to `tools/mo2-mcp/tests/acceptance-live.test.ts` that creates a 3-separator test profile, attempts cross-separator moves, and asserts post-move priorities. Currently no such test guards this case.

## Curator workaround (effective)

1. Disable mod via mo2-mcp (works fine).
2. Edit `meta.ini` notes with `[ARCHIVED]` marker via mo2-mcp (works fine, respects Qt INI quoting).
3. **Manually drag the mod in MO2 GUI left pane to the desired separator group**. BB84 verified this works around the broker bug.

## Out of scope

- This issue does NOT cover `toggle_mod` (works fine).
- This issue does NOT cover `edit_meta` (works fine, including Qt INI quoting per memory rule 18).
- This issue does NOT cover plugins.txt operations.

## Linked context

- Lane 3 v3 supplement: `D:\awesome-bgs-mod-master\.opencode\artifacts\bb84-starfield-lane3-preflight\report-v3-supplement.md`
- Phase A session log (this incident): orchestrator-delta session 2026-06-27, search "rbt_suitup_creations-cc"
- Project memory rule about parallel session worktrees: AGENTS.md "Parallel fixer dispatches share the working tree; commit your own paths only" (2026-06-17)
- Existing mo2-mcp T3 bug tracker: issue #14 (BUG-E plugins.txt auto-register + BUG-F parallel-plan lease + BUG-A stale PID cache)

## Filing instructions

Open GitHub issue at https://github.com/BB-84C/bgs-modding-superpowers/issues titled `mo2-mcp: send_mod_to cross-separator moves placed in wrong section + priority mode clamped to current section`, paste this file's content. Tag as `bug, mo2-mcp, broker, semantics`.
