import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

interface MockSidecar {
  call: (m: string, p: unknown) => Promise<unknown>;
  isReady: () => boolean;
  start: () => Promise<void>;
  stop: () => Promise<void>;
}

async function _fixture(sidecarBuilder?: (root: string) => MockSidecar): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-in-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+ExistingMod\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), "+ExistingMod\n", "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await mkdir(join(root, "mods"), { recursive: true });

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
  if (sidecarBuilder) {
    ctx.sidecar = sidecarBuilder(root) as unknown as ToolContext["sidecar"];
  }
  return { root, ctx };
}

describe("mo2_install", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-install.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_install")?.tier).toBe("T3");
  });

  it("plan throws sidecar_required without sidecar", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_install")!;
    await expect(
      tool.handler(
        { mode: "plan", archive_path: "/tmp/foo.7z", mod_name: "NewMod" },
        ctx,
      ),
    ).rejects.toThrow(/sidecar_required/);
  });

  it("plan throws fomod_choices_required when FOMOD has no choices", async () => {
    const { ctx } = await _fixture((root) => ({
      call: async (method, _params) => {
        if (method === "fomod.parse_choices") {
          return {
            fomod_name: "TestMod",
            pages: [{ name: "Step1", groups: [{ name: "G", type: "SelectAny", options: [{ name: "A", description: "", image: null, type: "Optional" }] }] }],
          };
        }
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    const tool = getTool("mo2_install")!;
    await expect(
      tool.handler(
        { mode: "plan", archive_path: "/tmp/fomod.7z", mod_name: "FomodMod" },
        ctx,
      ),
    ).rejects.toThrow(/fomod_choices_required/);
  });

  it("plan succeeds for non-FOMOD (parse_choices throws not_a_fomod)", async () => {
    const { ctx } = await _fixture((root) => ({
      call: async (method) => {
        if (method === "fomod.parse_choices") {
          throw new Error("not_a_fomod: no info.xml");
        }
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/simple.7z", mod_name: "SimpleMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; diff: string } };
    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("FOMOD=false");
  });

  it("BUG-19: non-FOMOD install with explicit empty choices uses archive extraction", async () => {
    const calls: string[] = [];
    const { root, ctx } = await _fixture((rootDir) => ({
      call: async (method, params) => {
        calls.push(method);
        if (method === "fomod.parse_choices") {
          throw new Error("not_a_fomod: no info.xml");
        }
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(join(dest, "data"), { recursive: true });
          await writeFile(join(dest, "data", "file1.txt"), "payload-1", "utf8");
          await writeFile(join(dest, "data", "file2.txt"), "payload-2", "utf8");
          return { files: ["data/file1.txt", "data/file2.txt"], file_count: 2, dest, format: "7z" };
        }
        if (method === "install.stage_fomod") {
          throw new Error("not_a_fomod: install.stage_fomod should not run for non-FOMOD empty choices");
        }
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));

    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/simple.7z", mod_name: "EmptyChoicesSimple", fomod_choices: [] },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string; diff: string } };
    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("FOMOD=false");

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { fomod_used: boolean } };

    expect(apply.ok).toBe(true);
    expect(apply.result.fomod_used).toBe(false);
    expect(calls).toContain("archive.extract_all");
    expect(calls).not.toContain("install.stage_fomod");
    expect(existsSync(join(root, "mods", "EmptyChoicesSimple", "data", "file1.txt"))).toBe(true);
    expect(existsSync(join(root, "mods", "EmptyChoicesSimple", "data", "file2.txt"))).toBe(true);
  });

  it("BUG-19: FOMOD plan treats explicit empty choices as missing choices", async () => {
    const { ctx } = await _fixture((root) => ({
      call: async (method, _params) => {
        if (method === "fomod.parse_choices") {
          return {
            fomod_name: "TestMod",
            pages: [{ name: "Step1", groups: [{ name: "G", type: "SelectAny", options: [{ name: "A", description: "", image: null, type: "Optional" }] }] }],
          };
        }
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    const tool = getTool("mo2_install")!;

    await expect(
      tool.handler(
        { mode: "plan", archive_path: "/tmp/fomod.7z", mod_name: "FomodMod", fomod_choices: [] },
        ctx,
      ),
    ).rejects.toThrow(/fomod_choices_required/);
  });

  it("plan rejects mod_name_exists", async () => {
    const { root, ctx } = await _fixture((_root) => ({
      call: async () => { throw new Error("not_a_fomod"); },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    await mkdir(join(root, "mods", "Existing"));
    const tool = getTool("mo2_install")!;
    await expect(
      tool.handler(
        { mode: "plan", archive_path: "/tmp/x.7z", mod_name: "Existing" },
        ctx,
      ),
    ).rejects.toThrow(/mod_name_exists/);
  });

  it("plan → apply simple archive: creates mod dir + meta.ini + modlist registration", async () => {
    const { root, ctx } = await _fixture((rootDir) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") {
          throw new Error("not_a_fomod");
        }
        if (method === "archive.extract_all") {
          // Simulate extraction by creating dest dir with one file
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "test.esp"), "fake-esp", "utf8");
          return { files: ["test.esp"], file_count: 1, dest, format: "7z" };
        }
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));

    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/test.7z", mod_name: "NewSimple", target_priority: "bottom" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { dest_path: string } };
    expect(apply.ok).toBe(true);
    expect(existsSync(join(root, "mods", "NewSimple", "test.esp"))).toBe(true);
    expect(existsSync(join(root, "mods", "NewSimple", "meta.ini"))).toBe(true);

    const meta = await readFile(join(root, "mods", "NewSimple", "meta.ini"), "utf8");
    expect(meta).toContain("installationFile=test.7z");
    expect(meta).toContain("gameName=fallout4");
    expect(meta).toContain("validated=true");

    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist).toContain("+NewSimple");

    expect(apply.result.snapshot_id).toMatch(/^[0-9a-f-]+$/);
    const rollback = await ctx.snapshots.restore(apply.result.snapshot_id!);
    expect(rollback.failed).toEqual([]);
    expect(existsSync(join(root, "mods", "NewSimple"))).toBe(false);
    expect(await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8")).toBe("+ExistingMod\n");
  });

  it("apply live broker path copies staged content into broker-created mod dir", async () => {
    const { root, ctx } = await _fixture((rootDir) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") {
          throw new Error("not_a_fomod");
        }
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "live.esp"), "fake-live", "utf8");
          return { files: ["live.esp"], file_count: 1, dest, format: "7z" };
        }
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked sidecar: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    const brokerCalls: Array<{ method: string; params: unknown }> = [];
    ctx.pipeClient = {
      call: async (method: string, params: unknown) => {
        brokerCalls.push({ method, params });
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        if (method === "installation.create_mod_from_directory") {
          const absolutePath = join(root, "mods", "LiveMod");
          await mkdir(absolutePath, { recursive: true });
          return { ok: true, result: { name: "LiveMod", absolute_path: absolutePath }, error: null };
        }
        if (method === "organizer.refresh") return { ok: true, result: { refreshed: true }, error: null };
        throw new Error(`unmocked broker: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];

    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/live.7z", mod_name: "LiveMod", target_priority: "bottom" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { dest_path: string; snapshot_id?: string } };

    expect(apply.ok).toBe(true);
    expect(apply.result.dest_path).toBe(join(root, "mods", "LiveMod"));
    expect(existsSync(join(root, "mods", "LiveMod", "live.esp"))).toBe(true);
    expect(existsSync(join(root, "mods", "LiveMod", "meta.ini"))).toBe(true);
    const meta = await readFile(join(root, "mods", "LiveMod", "meta.ini"), "utf8");
    expect(meta).toContain("installationFile=live.7z");
    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist).toContain("+LiveMod");
    // BUG-9 fix (2026-06-17): buildPlan now also runs assertActiveProfile,
    // which adds an extra profile.active call before the apply guard.
    expect(brokerCalls.map((call) => call.method)).toEqual([
      "profile.active", // buildPlan guard
      "profile.active", // applyMutation guard
      "installation.create_mod_from_directory",
    ]);
  });

  // BUG-9 fix (2026-06-17): cross-profile request is rejected at plan time.
  it("BUG-9: live plan blocks when requested profile is not the active MO2 profile", async () => {
    const { ctx } = await _fixture((rootDir) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "blocked.esp"), "fake", "utf8");
          return { files: ["blocked.esp"], file_count: 1, dest, format: "7z" };
        }
        throw new Error(`unmocked sidecar: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    ctx.pipeClient = {
      call: async (method: string) => {
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        throw new Error(`unexpected live mutation: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_install")!;

    await expect(tool.handler(
      { mode: "plan", archive_path: "/tmp/blocked.7z", mod_name: "BlockedLive", profile: "BB84自用" },
      ctx,
    )).rejects.toThrow(/cross_profile_live_mutation_blocked/);
    expect(existsSync(join(ctx.config.mo2Root, "mods", "BlockedLive"))).toBe(false);
  });

  it("apply offline path preserves the destPath clobber guard", async () => {
    const { root, ctx } = await _fixture((rootDir) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") {
          throw new Error("not_a_fomod");
        }
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "offline.esp"), "fake-offline", "utf8");
          return { files: ["offline.esp"], file_count: 1, dest, format: "7z" };
        }
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/offline.7z", mod_name: "OfflineMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    await mkdir(join(root, "mods", "OfflineMod"), { recursive: true });

    await expect(
      tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      ),
    ).rejects.toThrow(/mod_name_exists: OfflineMod/);
  });
});
