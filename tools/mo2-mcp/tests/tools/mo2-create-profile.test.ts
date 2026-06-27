import { describe, it, expect, beforeAll, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

const roots: string[] = [];

async function fixture(options: { withPipe?: boolean; profileInitThrows?: boolean; profileInitOkFalse?: boolean } = {}): Promise<{
  root: string;
  ctx: ToolContext;
  pipeCalls: Array<{ method: string; params: Record<string, unknown> }>;
}> {
  const root = await mkdtemp(join(tmpdir(), "mo2-profile-create-"));
  roots.push(root);
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+BaseMod\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "*Fallout4.esm\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "settings.ini"), "[General]\nfoo=bar\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "ignore.json"), "{}\n", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\n[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "full-control",
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

  const pipeCalls: Array<{ method: string; params: Record<string, unknown> }> = [];
  if (options.withPipe) {
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        if (method === "profile.initialize") {
          if (options.profileInitThrows) throw new Error("profile init kaboom");
          if (options.profileInitOkFalse) return { ok: false, error: { message: "profile init rejected" } };
          return { ok: true, result: { profile_dir: params.profile_dir, settings_applied: params.settings } };
        }
        throw new Error(`unmocked: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
  }
  return { root, ctx, pipeCalls };
}

describe("mo2_create_profile", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-create-profile.js");
  });

  afterEach(async () => {
    await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
  });

  it("plan throws profile_exists when target profile directory already exists", async () => {
    const { ctx } = await fixture();
    const tool = getTool("mo2_create_profile")!;

    await expect(tool.handler({ mode: "plan", name: "Default" }, ctx))
      .rejects.toThrow(/profile_exists: Default/);
  });

  it("plan diff mentions offline versus online path", async () => {
    const offline = await fixture();
    const online = await fixture({ withPipe: true });
    const tool = getTool("mo2_create_profile")!;

    const offlinePlan = (await tool.handler(
      { mode: "plan", name: "OfflineNew", from_profile: "Default" },
      offline.ctx,
    )) as { ok: boolean; result: { diff: string } };
    const onlinePlan = (await tool.handler(
      { mode: "plan", name: "OnlineNew" },
      online.ctx,
    )) as { ok: boolean; result: { diff: string } };

    expect(offlinePlan.result.diff).toBe("Create profile OfflineNew via offline path, clone modlist from Default");
    expect(onlinePlan.result.diff).toBe("Create profile OnlineNew via online path");
  });

  it("apply offline creates profile dir with empty modlist and archives", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_create_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "OfflineNew" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { profile_name: string; path: string; source: string; snapshot_id?: string } };

    expect(apply.result).toMatchObject({ profile_name: "OfflineNew", path: join(root, "profiles", "OfflineNew"), source: "offline_created" });
    expect(await readFile(join(root, "profiles", "OfflineNew", "modlist.txt"), "utf8")).toBe("");
    expect(await readFile(join(root, "profiles", "OfflineNew", "archives.txt"), "utf8")).toBe("");

    expect(apply.result.snapshot_id).toMatch(/^[0-9a-f-]+$/);
    const rollback = await ctx.snapshots.restore(apply.result.snapshot_id!);
    expect(rollback.failed).toEqual([]);
    expect(existsSync(join(root, "profiles", "OfflineNew"))).toBe(false);
  });

  it("apply with from_profile copies source txt and ini files only", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_create_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "CloneNew", from_profile: "Default" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    ) as { ok: boolean };

    expect(apply.ok).toBe(true);
    expect(await readFile(join(root, "profiles", "CloneNew", "modlist.txt"), "utf8")).toBe("+BaseMod\n");
    expect(await readFile(join(root, "profiles", "CloneNew", "plugins.txt"), "utf8")).toBe("*Fallout4.esm\n");
    expect(await readFile(join(root, "profiles", "CloneNew", "settings.ini"), "utf8")).toBe("[General]\nfoo=bar\n");
    expect(existsSync(join(root, "profiles", "CloneNew", "ignore.json"))).toBe(false);
  });

  it("apply online calls profile.initialize and returns online_initialized", async () => {
    const { root, ctx, pipeCalls } = await fixture({ withPipe: true });
    const tool = getTool("mo2_create_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "OnlineNew", settings: ["MODS", "SAVEGAMES"] },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { source: string } };

    expect(apply.result.source).toBe("online_initialized");
    expect(pipeCalls).toEqual([
      { method: "profile.initialize", params: { profile_dir: join(root, "profiles", "OnlineNew"), settings: ["MODS", "SAVEGAMES"] } },
      {
        method: "system.log_apply",
        params: expect.objectContaining({
          tool: "mo2_create_profile",
          profile: "OnlineNew",
          summary: "created profile \"OnlineNew\" settings=MODS,SAVEGAMES",
        }),
      },
    ]);
  });

  it("apply online broker throw falls back to offline-created profile with warning", async () => {
    const { root, ctx } = await fixture({ withPipe: true, profileInitThrows: true });
    const tool = getTool("mo2_create_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "FallbackNew" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { source: string; warning: string } };

    expect(apply.result.source).toBe("online_init_failed_offline_fallback");
    expect(apply.result.warning).toContain("profile init kaboom");
    expect(existsSync(join(root, "profiles", "FallbackNew", "modlist.txt"))).toBe(true);
  });
});
