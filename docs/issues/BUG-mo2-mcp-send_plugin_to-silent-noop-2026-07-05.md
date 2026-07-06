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

## Resolution (2026-07-06)

Root cause was MO2's plugins.txt persistence race, not xEdit/VFS locking or a new-plugin registration gap. Source audit against MO2 master showed:

- `IPluginList::setPriority` mutates plugin order in memory and updates the plugin pane through model `dataChanged` signals, but `pluginlist.h` documents that this does **not immediately cause anything to be written to disc**.
- `PluginList::writePluginsList` is wired through `DelayedFileWriterBase::write`; `delayedfilewriter.h` defaults that write delay to 200 ms.
- `OrganizerCore::refresh(saveChanges=True)` saves the modlist via `writeModlistNow`, but does not force-flush plugins.txt. Its DirectoryRefresher completion path runs `refreshESPList(force=true)`, causing `PluginList::refresh` to re-read plugins.txt from disk.

The old broker called `organizer.refresh()` immediately after `plugin_list.setPriority`. If the refresh/rescan beat the 200 ms delayed writer, stale plugins.txt state was loaded over the fresh in-memory priority, and the delayed writer later flushed the reverted order back to disk. MO2's own GUI drag/drop path does not call `refresh()` for plugin moves; the setPriority/dataChanged cascade is the GUI refresh.

Fix shape:

- `plugins.set_priority`: removed the racy `organizer.refresh()` call, added same-closure readback, and returns `priority_not_applied` with `{name, requested_priority, before_priority, final_priority}` if mobase refuses the move. Successful responses now report `gui_refreshed: true` and `persist: "deferred-writer-200ms"` to make the disk-flush contract explicit.
- `mods.set_priority`: kept `organizer.refresh()` because modlist refresh does flush via `writeModlistNow`, but moved readback after refresh and now emits the same `priority_not_applied` error if post-refresh state differs from the requested priority.
- `mo2_send_plugin_to`: `new_priority` now echoes the broker-verified `actual_priority` instead of the TS target, broker errors include their code in the thrown message, and live success performs best-effort plugins.txt polling for the expected relative order (`disk_flush_confirmed`).

Remaining known window: an **external** `organizer.refresh()` within roughly 200 ms of a plugin move can still revert the change before MO2's delayed plugins.txt writer fires. There is no public mobase API to force-flush plugins.txt (`IPluginList` has no save/flush; the C++ `OrganizerCore::savePluginList` is not exposed), so callers must tolerate the deferred persistence window unless MO2 adds an upstream flush API.
