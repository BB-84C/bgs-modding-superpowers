import { describe, it, expect, beforeAll, vi } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { EventEmitter } from "node:events";
import { spawn } from "node:child_process";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

vi.mock("node:child_process", () => ({
  spawn: vi.fn(),
}));

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-run-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "mods"), { recursive: true });
  await writeFile(
    join(root, "ModOrganizer.ini"),
    [
      "[General]",
      "game=fallout4",
      "[Settings]",
      `base_directory=${root}`,
      "[customExecutables]",
      "size=1",
      "1\\title=xEdit",
      "1\\binary=C:/Tools/xEdit/xEdit.exe",
      "1\\arguments=-FO4",
      "",
    ].join("\n"),
    "utf8",
  );

  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    sessionId: "test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
    audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
  };
  return { root, ctx };
}

describe("mo2_run_tool", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-run-tool.js");
  });

  it("plan returns diff mentioning the configured executable binary", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_run_tool")!;
    const plan = (await tool.handler(
      { mode: "plan", title: "xEdit" },
      ctx,
    )) as { ok: boolean; result: { diff: string } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("C:/Tools/xEdit/xEdit.exe");
  });

  it("plan throws executable_not_found and lists configured titles", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_run_tool")!;

    await expect(
      tool.handler({ mode: "plan", title: "LOOT" }, ctx),
    ).rejects.toThrow(/executable_not_found: LOOT \(configured: xEdit\)/);
  });

  it("apply live starts and waits using snake_case broker methods", async () => {
    const { ctx } = await _fixture();
    const calls: Array<{ method: string; params: Record<string, unknown> }> = [];
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        calls.push({ method, params });
        if (method === "organizer.start_application") {
          return { ok: true, result: { handle: 42, executable: "xEdit" } };
        }
        if (method === "organizer.wait_for_application") {
          return { ok: true, result: { handle: 42, success: true, exit_code: 0 } };
        }
        throw new Error(`unmocked: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_run_tool")!;
    const plan = (await tool.handler(
      { mode: "plan", title: "xEdit", wait: true },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { handle: number; exit_code: number; success: boolean } };

    expect(apply.ok).toBe(true);
    expect(apply.result).toMatchObject({ handle: 42, exit_code: 0, success: true });
    expect(calls[0]).toEqual({
      method: "organizer.start_application",
      params: {
        executable: "xEdit",
        args: [],
        cwd: "",
        profile: "Default",
        forcedCustomOverwrite: "",
        ignoreCustomOverwrite: false,
      },
    });
    expect(calls[1]).toEqual({
      method: "organizer.wait_for_application",
      params: { handle: 42, refresh: true },
    });
  });

  it("apply offline spawns ModOrganizer.exe with run -e title", async () => {
    const { root, ctx } = await _fixture();
    const child = new EventEmitter() as EventEmitter & { pid: number; unref: () => void };
    child.pid = 1234;
    child.unref = vi.fn();
    vi.mocked(spawn).mockReset();
    vi.mocked(spawn).mockReturnValue(child as never);

    const tool = getTool("mo2_run_tool")!;
    const plan = (await tool.handler(
      { mode: "plan", title: "xEdit" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { pid: number; waiting: boolean; source: string } };

    expect(apply.ok).toBe(true);
    expect(apply.result).toMatchObject({ pid: 1234, waiting: false, source: "offline_cli" });
    expect(spawn).toHaveBeenCalledWith(
      join(root, "ModOrganizer.exe"),
      ["-p", "Default", "run", "-e", "xEdit"],
      { detached: true, stdio: "ignore" },
    );
    expect(child.unref).toHaveBeenCalledOnce();
  });
});
