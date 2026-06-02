# CC Follow-up MCP + Skill Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the three post-acceptance issues surfaced by Claude Code: remove game-specific / harness-specific assumptions from load-order skills, add xEdit stop/restart + dirty-state safety to the MCP, and make the install story unambiguous.

**Architecture:** Keep the existing non-blocking MCP state machine and extend it with explicit lifecycle verbs (`xedit_stop`, `xedit_restart`) plus dirty-state probing via the daemon's `session.get_dirty_state`. Keep packaging changes minimal: clarify that the Python plugin is the real MO2 integration and keep Codex's local workaround out of shipped guidance. Skills are updated to be game-agnostic and harness-agnostic.

**Tech Stack:** TypeScript 5.x, Node 22+, `@modelcontextprotocol/sdk`, PowerShell 7+, existing xEdit daemon / MO2 control-plane harness.

---

## File Structure

```
skills/
  using-bgs-modding-superpowers/SKILL.md         (modify MCP tool inventory)
  xedit-automation/SKILL.md                      (modify launch + load-order guidance)
  writing-bgs-load-order/SKILL.md                (remove FO4-only / .opencode assumptions)

tools/xedit-mcp/
  src/
    index.ts                                     (add xedit_stop/xedit_restart handlers + state transitions)
    tools/
      session.ts                                 (read current session behavior if needed)
      call.ts                                    (already fixed args coercion; may only need docs/comments)
  dist/                                          (rebuilt JS)

docs/internal/superpowers/plans/
  2026-06-01-cc-followup-mcp-and-skill-fixes.md  (this plan)
```

## Task 1: Make `writing-bgs-load-order` game-agnostic and harness-agnostic

**Files:**
- Modify: `skills/writing-bgs-load-order/SKILL.md`

- [ ] Remove the hardcoded vanilla-master table.
- [ ] Replace it with a rule: the agent must infer hardcoded / official masters from the target game's actual MO2-managed install (or from `xedit_status`/`xedit_call("files.list")` once xEdit is ready) and avoid editing them.
- [ ] Replace any `.opencode/artifacts/<task>/plugins.txt` language with a generic phrase like `an agent-owned artifacts path` and give examples from multiple harnesses (`.opencode/artifacts/`, `.claude/artifacts/`, temp dir, etc.) without privileging OpenCode.
- [ ] Keep the routing matrix and asterisk-format semantics intact.

## Task 2: Add explicit lifecycle MCP verbs + dirty-state warning

**Files:**
- Modify: `tools/xedit-mcp/src/index.ts`
- Modify: `skills/using-bgs-modding-superpowers/SKILL.md`
- Modify: `skills/xedit-automation/SKILL.md`

- [ ] Add `xedit_stop` MCP tool:
  - If daemon state is `not_started` -> return `{ ok: true, status: "not_started" }`.
  - If daemon state is `starting` -> best-effort stop the launch if a PID exists; otherwise clear state.
  - If daemon state is `ready` -> call daemon `session.get_dirty_state` first.
  - If dirty and `force !== true` -> return non-blocking refusal envelope with `code: "dirty_state"`, `dirtyFiles`, `unsavedChangeCount`, and hint asking the agent to decide abandon vs continue.
  - If not dirty OR `force === true` -> stop daemon, clear cached state/toolset, return `{ ok: true, status: "stopped" }`.
- [ ] Add `xedit_restart` MCP tool:
  - Accept the same launch override args as `xedit_start` (`launcherPath`, `gameMode`, `dataPath`, `pluginsFile`, `moProfile`) plus `force?: boolean`.
  - Internally run the same dirty-state logic as `xedit_stop`, then kick off a fresh background launch using the new overrides.
  - Return immediately with `status: "starting"` (never block).
- [ ] Update `TOOL_DEFINITIONS` so `tools/list` exposes the new verbs and their argument semantics.
- [ ] In `using-bgs-modding-superpowers`, update the MCP tools section / canonical lifecycle pattern to mention `xedit_stop` and `xedit_restart` and the dirty-state safety behavior.
- [ ] In `xedit-automation`, add guidance: use `xedit_restart({ pluginsFile, dataPath, ... })` instead of manual `/mcp reconnect` when iterating on custom plugin lists.

## Task 3: Clarify current dirty-state support

**Files:**
- Modify: `skills/xedit-automation/xedit-knowledgebase.md`

- [ ] Add a short note under `session.*` or `Mutation policy` that the daemon already exposes `session.get_dirty_state` and the MCP can reach it today via `xedit_call({ command: "session.get_dirty_state", args: {} })` once the daemon is ready.
- [ ] Document that `xedit_stop` / `xedit_restart` now surface this automatically, so agents usually won't need the passthrough.

## Task 4: Rebuild and verify

**Files:**
- Rebuild: `tools/xedit-mcp/dist/**`

- [ ] Run `npm run build` in `tools/xedit-mcp/`.
- [ ] Verify `node --check dist/index.js` passes.
- [ ] Sanity-check the stdio server stays alive after initialize + `tools/list`.
- [ ] Confirm `tools/list` now exposes `xedit_stop` and `xedit_restart`.

## Task 5: Commit and handoff

- [ ] Commit all changes in one logical commit.
- [ ] Report back to the user with:
  - the answer to "can the current MCP check dirty?" -> yes, via daemon `session.get_dirty_state`, now exposed directly in stop/restart flow;
  - the exact retest sequence for CC (`xedit_start` / `xedit_status` / `xedit_restart`);
  - the note that load-order skill is now game-agnostic and harness-agnostic.
