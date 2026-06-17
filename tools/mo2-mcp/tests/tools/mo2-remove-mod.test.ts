import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, rm, cp } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";
import { releaseLeaseLocks } from "../../src/lease-lock.js";

vi.mock("node:fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:fs/promises")>();
  return {
    ...actual,
    cp: vi.fn(actual.cp),
    rm: vi.fn(actual.rm),
  };
});

interface MockPipeCall {
  method: string;
  params: Record<string, unknown>;
}

const roots: string[] = [];

async function fixture(options: { createMod?: boolean; withPipe?: boolean } = {}): Promise<{
  root: string;
  ctx: ToolContext;
  pipeCalls: MockPipeCall[];
}> {
  const root = await mkdtemp(join(tmpdir(), "mo2-remove-"));
  roots.push(root);
  await mkdir(join(root, "mods"), { recursive: true });
  if (options.createMod) {
    await mkdir(join(root, "mods", "Target"), { recursive: true });
    await writeFile(join(root, "mods", "Target", "file.txt"), "payload", "utf8");
  }
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await mkdir(join(root, "profiles", "Alt"), { recursive: true });
  await mkdir(join(root, "profiles", "Other"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+Target\n+Keep\n-TargetExtra\n", "utf8");
  await writeFile(join(root, "profiles", "Alt", "modlist.txt"), "-Target\n+Keep\n", "utf8");
  await writeFile(join(root, "profiles", "Other", "modlist.txt"), "+Different\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\n[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "full-control",
      allowedProfiles: ["Default", "Alt", "Other"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    sessionId: "test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
    audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
  };

  const pipeCalls: MockPipeCall[] = [];
  if (options.withPipe) {
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        if (method === "mods.remove") return { ok: true, result: { name: params.name, removed: true } };
        if (method === "organizer.refresh") return { ok: true, result: { refreshed: true } };
        throw new Error(`unmocked: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
  }

  return { root, ctx, pipeCalls };
}

describe("mo2_remove_mod", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-remove-mod.js");
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
  });

  it("plan throws mod_not_found when mod dir is absent", async () => {
    const { ctx } = await fixture({ createMod: false });
    const tool = getTool("mo2_remove_mod")!;

    await expect(tool.handler({ mode: "plan", name: "Target" }, ctx))
      .rejects.toThrow(/mod_not_found: Target/);
  });

  it("plan diff reflects backup_first default true versus explicit false", async () => {
    const { root, ctx } = await fixture({ createMod: true });
    const tool = getTool("mo2_remove_mod")!;

    const withBackup = (await tool.handler(
      { mode: "plan", name: "Target" },
      ctx,
    )) as { ok: boolean; result: { planId: string; diff: string; affected_files: string[] } };
    expect(withBackup.ok).toBe(true);
    const firstPlan = ctx.plans.get(withBackup.result.planId)!;
    await releaseLeaseLocks(ctx.config.mo2Root, firstPlan.leaseLockTargetHashes, firstPlan.planId);
    ctx.plans.consume(firstPlan.planId);
    const withoutBackup = (await tool.handler(
      { mode: "plan", name: "Target", backup_first: false },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };
    expect(withoutBackup.ok).toBe(true);

    expect(withBackup.result.diff).toBe(`Backup + DELETE mod folder ${join(root, "mods", "Target")} + remove from all profile modlists`);
    expect(withoutBackup.result.diff).toBe(`DELETE mod folder ${join(root, "mods", "Target")} + remove from all profile modlists`);
    expect(withBackup.result.affected_files).toEqual([join(root, "mods", "Target")]);
  });

  it("apply with backup_first true copies to Targetbackup0 and calls live mods.remove", async () => {
    const { root, ctx, pipeCalls } = await fixture({ createMod: true, withPipe: true });
    const tool = getTool("mo2_remove_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "Target" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    vi.clearAllMocks();

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { removed: string; backup_name?: string } };

    expect(cp).toHaveBeenCalledWith(join(root, "mods", "Target"), join(root, "mods", "Targetbackup0"), { recursive: true });
    expect(pipeCalls).toEqual([
      { method: "mods.remove", params: { name: "Target" } },
    ]);
    expect(apply.result).toMatchObject({ removed: "Target", backup_name: "Targetbackup0" });
  });

  it("apply with backup_first true increments when Targetbackup0 already exists", async () => {
    const { root, ctx } = await fixture({ createMod: true, withPipe: true });
    await mkdir(join(root, "mods", "Targetbackup0"), { recursive: true });
    const tool = getTool("mo2_remove_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "Target" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    vi.clearAllMocks();

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { backup_name?: string } };

    expect(cp).toHaveBeenCalledWith(join(root, "mods", "Target"), join(root, "mods", "Targetbackup1"), { recursive: true });
    expect(apply.result.backup_name).toBe("Targetbackup1");
  });

  it("apply with backup_first false does not copy before live remove", async () => {
    const { ctx, pipeCalls } = await fixture({ createMod: true, withPipe: true });
    const tool = getTool("mo2_remove_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "Target", backup_first: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    vi.clearAllMocks();

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { backup_name?: string } };

    const backupCopies = vi.mocked(cp).mock.calls.filter(([, dest]) => String(dest).includes("Targetbackup"));
    expect(backupCopies).toEqual([]);
    expect(pipeCalls).toEqual([
      { method: "mods.remove", params: { name: "Target" } },
    ]);
    expect(apply.result.backup_name).toBeUndefined();
  });

  it("apply offline removes folder and scrubs matching modlist lines only", async () => {
    const { root, ctx } = await fixture({ createMod: true, withPipe: false });
    const tool = getTool("mo2_remove_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "Target", backup_first: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    vi.clearAllMocks();

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { removed: string; backup_name?: string } };

    expect(apply.ok).toBe(true);
    expect(rm).toHaveBeenCalledWith(join(root, "mods", "Target"), { recursive: true, force: true });
    expect(await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8"))
      .toBe("+Keep\n-TargetExtra\n");
    expect(await readFile(join(root, "profiles", "Alt", "modlist.txt"), "utf8"))
      .toBe("+Keep\n");
    expect(await readFile(join(root, "profiles", "Other", "modlist.txt"), "utf8"))
      .toBe("+Different\n");
  });

  // BUG-15 fix (2026-06-17): broker-alive apply with backup_first=false used
  // to take the broker-ok branch and skip _scrubAllProfileModlists, leaving
  // orphan +Target / -Target rows in profiles/<*>/modlist.txt. After the
  // unified fix, the filesystem scrub runs regardless of the broker code
  // path. Phase 4 evidence: phase4final-beta-B.3.8.json (backup_first=false
  // returned profiles_updated:[] while +E2E-Throwaway-232817 lingered in
  // modlist.txt).
  it("BUG-15: live apply with backup_first:false scrubs orphan modlist rows from all profiles", async () => {
    const { root, ctx, pipeCalls } = await fixture({ createMod: true, withPipe: true });
    const tool = getTool("mo2_remove_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "Target", backup_first: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    vi.clearAllMocks();

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as {
      ok: boolean;
      result: { removed: string; backup_name?: string; profiles_updated: string[] };
    };

    expect(apply.ok).toBe(true);
    expect(apply.result.backup_name).toBeUndefined();
    // Broker is still called (informational), but the filesystem scrub is
    // what guarantees on-disk durability.
    expect(pipeCalls.map((c) => c.method)).toContain("mods.remove");
    // Mod folder is gone, even though the broker mock did not delete it.
    expect(existsSync(join(root, "mods", "Target"))).toBe(false);
    // Every profile modlist that referenced Target had the row scrubbed.
    expect(await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8"))
      .toBe("+Keep\n-TargetExtra\n");
    expect(await readFile(join(root, "profiles", "Alt", "modlist.txt"), "utf8"))
      .toBe("+Keep\n");
    expect(await readFile(join(root, "profiles", "Other", "modlist.txt"), "utf8"))
      .toBe("+Different\n");
    // profiles_updated reflects the actual on-disk changes (Default + Alt
    // had Target rows; Other did not).
    expect([...apply.result.profiles_updated].sort()).toEqual(["Alt", "Default"]);
  });
});
