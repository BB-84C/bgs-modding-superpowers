# BUG: mo2_send_plugin_to live-mode apply reports ok but is a silent no-op

> **GitHub issue: https://github.com/BB-84C/bgs-modding-superpowers/issues/22** (filed 2026-07-05, BB84 将在 parallel session 修复)
> **2026-07-05 追加判别 (最终证据矩阵见 issue #22)**: (a) xEdit 完全关闭后 rows 复现 → VFS-lock 理论排除; (b) broker 内存态 (`mo2_pluginlist enrich`) 同样未变 → 非 plugins.txt 写回滞后; (c) 预存插件 `BB84_DevKit.esm` 第一次挪动成功、紧接的两次回挪全部 no-op → 非"新装插件"单因子, 呈竞态/连续挪动敏感; (d) 头号嫌疑 = mutation 路径新增的 auto GUI refresh 用旧态回读冲掉刚 set 的 priority (45-memory rules 1-2 同族)。当前残留态: DevKit 在 fuel/O2 之间 (line 136, 记录不相交无害), Default_Settings_Patch 在末位 (功能等价)。

**Date**: 2026-07-05 | **Env**: D:\Starfield MO2, profile BB84自用2, MO2 live (broker connected, pid 39596), 177-line plugins.txt, 12 foreign officials

## Symptom

`mo2_send_plugin_to` (live mode, broker path) `apply` returns `ok:true, noop:false, gui_refreshed:true, requested_priority==actual_priority`, but neither plugins.txt on disk nor the broker's own in-memory plugin list actually changes. The plugin stays at its original position.

## Reproductions (2 distinct incidents)

1. **2026-07-05 (earlier session)**: `caracal_venera.esm` move 157→126 — first apply silently no-op'd (reported ok, no change); **retry worked**.
2. **2026-07-05 (this session)**: `BB84_Default_Settings_Patch.esm` (fresh install at end of plugins.txt, mobase priority 187):
   - apply #1: `wins_over BB84_Starvival_O2_Off_Patch.esm` → requested 147, actual 150, noop:false — file unchanged (line 177/end).
   - apply #2: `wins_over rbt_roverhaul.esm` → requested 150, actual 150 — file unchanged.
   - apply #3 (fresh plan, same target): requested 150, actual 150 — file unchanged.
   - Post-check via `mo2_pluginlist enrich:true`: target slot 150 still occupied by `rbt_skeletonkey.esm`; our plugin still at priority 187 **in the broker's own enriched readback**. So the failure is not a plugins.txt flush lag — `IPluginList.setPriority` either did not take effect or was reverted by an immediate refresh.
   - **Retry did NOT fix** (unlike incident 1).

## Notes / hypotheses

- apply #1 oddity: `requested_priority:147, actual_priority:150` in the same response — the wins_over target computation and the broker's accepted value disagree; response also carried `new_priority:147`, inconsistent with `actual_priority:150`.
- Possible classes: (a) broker `plugins.set_priority` accepted but MO2 re-sorts/reverts on refresh (masters/ESM-type auto-sort?), (b) refresh race similar to Rule 1/2 in 45-mo2-mcp-internals (mutation + refresh must share the main-thread closure), (c) freshly-installed plugin not yet fully registered in the plugin list when setPriority ran (incident 2 plugin was installed ~1 min earlier via mo2_install).
- Impact: agent believes the move happened; only external readback catches it. Same "reported ok but no change" class as the caracal incident — now with a same-session broker-readback proof.

## Suggested fix direction

- After live setPriority, re-read `plugin_list.priority(name)` inside the same broker closure and fail the call if it does not match the requested value (readback-verify in-handler instead of trusting the setter).
- Surface MO2's auto-sort/revert reason if detectable.

## Workaround used

Accepted end-of-list position for the defaults patch (functionally equivalent: loads after masters, wins its 3 overrides). For mandatory moves: retry once; if still no-op, fall back to MO2 GUI drag or offline rewrite with MO2 closed.
