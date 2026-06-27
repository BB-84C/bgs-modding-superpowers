import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { dispatchToolCall } from "../../src/dispatch.js";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";
import { FomodChoicesRequiredError } from "../../src/fomod-required-error.js";

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
    const caught = await tool.handler(
      { mode: "plan", archive_path: "/tmp/fomod.7z", mod_name: "FomodMod" },
      ctx,
    ).then(() => undefined, (e: unknown) => e);

    expect(caught).toBeInstanceOf(FomodChoicesRequiredError);
    const err = caught as FomodChoicesRequiredError;
    expect(err.message).toMatch(/fomod_choices_required/);
    expect(err.code).toBe("fomod_choices_required");
    expect(Array.isArray(err.details.fomod_tree.pages)).toBe(true);
    expect(err.details.fomod_tree.pages[0]?.groups[0]?.options[0]?.name).toBe("A");
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

    const caught = await tool.handler(
      { mode: "plan", archive_path: "/tmp/fomod.7z", mod_name: "FomodMod", fomod_choices: [] },
      ctx,
    ).then(() => undefined, (e: unknown) => e);

    expect(caught).toBeInstanceOf(FomodChoicesRequiredError);
    const err = caught as FomodChoicesRequiredError;
    expect(err.code).toBe("fomod_choices_required");
    expect(Array.isArray(err.details.fomod_tree.pages)).toBe(true);
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
      { mode: "plan", archive_path: "/tmp/test.7z", mod_name: "NewSimple", target_priority: "gui_bottom" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { dest_path: string; final_priority: number; _meta: Record<string, string>; snapshot_id?: string } };
    expect(apply.ok).toBe(true);
    expect(existsSync(join(root, "mods", "NewSimple", "test.esp"))).toBe(true);
    expect(existsSync(join(root, "mods", "NewSimple", "meta.ini"))).toBe(true);

    const meta = await readFile(join(root, "mods", "NewSimple", "meta.ini"), "utf8");
    expect(meta).toContain("installationFile=test.7z");
    // Note: meta.ini gameName field expects TitleCase (e.g. "Fallout4"), NOT
    // the lowercase internal key. The bugfix in mo-ini.ts resolveGameName()
    // (2026-06-24, BB84 Starfield audit round) maps the lowercase `game=`
    // value from ModOrganizer.ini back to its TitleCase display name via
    // GAME_KEY_TO_NAME. Pre-fix this wrote `gameName=fallout4` which was
    // wrong but harmless (no consumer of the field cared); post-fix it
    // writes the correct `gameName=Fallout4`.
    expect(meta).toContain("gameName=Fallout4");
    expect(meta).toContain("validated=true");

    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist).toContain("+NewSimple");
    expect(modlist.split(/\r?\n/)[0]).toBe("+NewSimple");
    expect(apply.result.final_priority).toBe(1);
    expect(apply.result._meta.priority_convention).toBe("mobase_full_space_higher_wins");

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
        if (method === "mods.list") return { ok: true, result: { mods: [{ name: "LiveMod", priority: 1 }] }, error: null };
        if (method === "plugins.missing_masters") return {
          ok: true,
          result: { warnings: [], scanned_count: 1, enabled_count: 1 },
          error: null,
        };
        throw new Error(`unmocked broker: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];

    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/live.7z", mod_name: "LiveMod", target_priority: "gui_bottom" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { dest_path: string; snapshot_id?: string; pluginWarnings?: unknown } };

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
    // BUG-14 BUG-E fix (issue #14): apply now calls organizer.refresh
    // after writing plugins.txt so MO2's in-memory plugin list re-reads
    // the freshly-registered plugin.
    // Plugin-warning auto-poll now follows the refresh so agents see any
    // missing-master containment breach caused by the newly-enabled plugin.
    expect(brokerCalls.map((call) => call.method)).toEqual([
      "profile.active", // buildPlan guard
      "profile.active", // applyMutation guard
      "installation.create_mod_from_directory",
      "organizer.refresh", // post-plugins.txt refresh (BUG-14 BUG-E)
      "mods.list", // final_priority readback
      "system.log_apply",
      "plugins.missing_masters",
    ]);
    expect(apply.result.pluginWarnings).toMatchObject({ warnings: [], scannedCount: 1, enabledCount: 1 });
  });

  it("Phase 3: target_priority gui_top places installed mod at GUI top / priority 0", async () => {
    const { root, ctx } = await _fixture((_root) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "GuiTop.esp"), "fake", "utf8");
          return { files: ["GuiTop.esp"], file_count: 1, dest, format: "zip" };
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
      { mode: "plan", archive_path: "/tmp/gui-top.zip", mod_name: "GuiTop", target_priority: "gui_top" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { final_priority: number } };

    expect(apply.ok).toBe(true);
    expect(apply.result.final_priority).toBe(0);
    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist.trim().split(/\r?\n/)).toEqual(["+ExistingMod", "+GuiTop"]);
  });

  it("Phase 3: integer target_priority is not silently ignored and lands at requested priority", async () => {
    const { root, ctx } = await _fixture((_root) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "IntegerPriority.esp"), "fake", "utf8");
          return { files: ["IntegerPriority.esp"], file_count: 1, dest, format: "zip" };
        }
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+High\n+Mid\n+Low\n", "utf8");
    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/int.zip", mod_name: "IntegerPriority", target_priority: 1 },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { final_priority: number } };

    expect(apply.ok).toBe(true);
    expect(apply.result.final_priority).toBe(1);
    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist.trim().split(/\r?\n/)).toEqual(["+High", "+Mid", "+IntegerPriority", "+Low"]);
  });

  it("Phase 3: old target_priority literals are a hard-break invalid_arguments", async () => {
    const { ctx } = await _fixture((_root) => ({
      call: async (method) => {
        if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));

    for (const oldLiteral of ["top", "bottom"]) {
      const result = await dispatchToolCall({
        toolName: "mo2_install",
        rawArgs: { mode: "plan", archive_path: "/tmp/old.zip", mod_name: "OldLiteral", target_priority: oldLiteral },
        ctx,
        rules: [],
      });
      const env = JSON.parse(result.content[0].text) as { ok: boolean; error: { code: string; field_errors: Record<string, string[]> } };
      expect(result.isError).toBe(true);
      expect(env.ok).toBe(false);
      expect(env.error.code).toBe("invalid_arguments");
      expect(env.error.field_errors.target_priority.join("\n")).toContain("Invalid input");
    }
  });

  it("Phase 3: live integer target_priority calls broker mods.set_priority and reports readback final_priority", async () => {
    const { root, ctx } = await _fixture((_root) => ({
      call: async (method, params) => {
        if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
        if (method === "archive.extract_all") {
          const dest = (params as { dest: string }).dest;
          await mkdir(dest, { recursive: true });
          await writeFile(join(dest, "LiveInteger.esp"), "fake", "utf8");
          return { files: ["LiveInteger.esp"], file_count: 1, dest, format: "zip" };
        }
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked sidecar: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    }));
    await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+High\n+Mid\n+Low\n", "utf8");
    const brokerCalls: Array<{ method: string; params: unknown }> = [];
    ctx.pipeClient = {
      call: async (method: string, params: unknown) => {
        brokerCalls.push({ method, params });
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        if (method === "installation.create_mod_from_directory") {
          const absolutePath = join(root, "mods", "LiveInteger");
          await mkdir(absolutePath, { recursive: true });
          return { ok: true, result: { name: "LiveInteger", absolute_path: absolutePath }, error: null };
        }
        if (method === "mods.set_priority") return { ok: true, result: { name: "LiveInteger", actual_priority: (params as { priority: number }).priority }, error: null };
        if (method === "mods.list") return { ok: true, result: { mods: [{ name: "LiveInteger", priority: 1 }] }, error: null };
        if (method === "organizer.refresh") return { ok: true, result: { refreshed: true }, error: null };
        if (method === "plugins.missing_masters") return { ok: true, result: { warnings: [], scanned_count: 1, enabled_count: 1 }, error: null };
        throw new Error(`unmocked broker: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_install")!;
    const plan = (await tool.handler(
      { mode: "plan", archive_path: "/tmp/live-int.zip", mod_name: "LiveInteger", target_priority: 1 },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { final_priority: number } };

    expect(apply.ok).toBe(true);
    expect(brokerCalls.find((c) => c.method === "mods.set_priority")?.params).toMatchObject({ name: "LiveInteger", priority: 1 });
    expect(brokerCalls.some((c) => c.method === "mods.list")).toBe(true);
    expect(apply.result.final_priority).toBe(1);
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

  // BUG-14 BUG-D + BUG-E regression (issue #14):
  //   - BUG-D: archive wraps content in a top-level Data/ directory; install
  //     must flatten so the plugin lands at mods/<name>/<plugin>.esm, not
  //     mods/<name>/Data/<plugin>.esm (where the MO2 VFS double-prefixes it).
  //   - BUG-E: install must register the discovered plugin in plugins.txt
  //     so the agent doesn't have to do a separate N×toggle_plugin call to
  //     activate it.
  describe("BUG-14 BUG-D + BUG-E: install flattens Data/ wrapper and registers plugins", () => {
    it("flattens Data/ wrapper produced by typical BGS archives", async () => {
      const { root, ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            // Real-world BB84 case: Astrogate v5.8 ships its ESMs inside
            // a top-level Data/ directory. Simulate that exact layout.
            const dest = (params as { dest: string }).dest;
            await mkdir(join(dest, "Data"), { recursive: true });
            await writeFile(join(dest, "Data", "Astrogate.esm"), "fake-esm", "utf8");
            await writeFile(
              join(dest, "Data", "AstrogateGravJumpMod.esm"),
              "fake-esm-2",
              "utf8",
            );
            await writeFile(
              join(dest, "Data", "Astrogate - Main.ba2"),
              "fake-ba2",
              "utf8",
            );
            return { files: ["Data/Astrogate.esm", "Data/AstrogateGravJumpMod.esm", "Data/Astrogate - Main.ba2"], file_count: 3, dest, format: "zip" };
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
        { mode: "plan", archive_path: "/tmp/astrogate.zip", mod_name: "Astrogate" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean; result: { plugins_registered: string[] } };

      expect(apply.ok).toBe(true);
      // Pre-fix: files lived at mods/Astrogate/Data/<plugin>.esm.
      // Post-fix: files at mods/Astrogate/<plugin>.esm (Data/ flattened).
      expect(existsSync(join(root, "mods", "Astrogate", "Astrogate.esm"))).toBe(true);
      expect(existsSync(join(root, "mods", "Astrogate", "AstrogateGravJumpMod.esm"))).toBe(true);
      expect(existsSync(join(root, "mods", "Astrogate", "Astrogate - Main.ba2"))).toBe(true);
      // Data/ directory should not survive the flatten.
      expect(existsSync(join(root, "mods", "Astrogate", "Data"))).toBe(false);
      // plugins.txt registration (BUG-E) — both ESMs added.
      expect(apply.result.plugins_registered).toEqual([
        "Astrogate.esm",
        "AstrogateGravJumpMod.esm",
      ]);
    });

    it("does not flatten when plugin already at staging root (most simple archives)", async () => {
      const { root, ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(dest, { recursive: true });
            await writeFile(join(dest, "FlatMod.esp"), "fake", "utf8");
            return { files: ["FlatMod.esp"], file_count: 1, dest, format: "zip" };
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
        { mode: "plan", archive_path: "/tmp/flat.zip", mod_name: "FlatMod" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean };
      expect(apply.ok).toBe(true);
      expect(existsSync(join(root, "mods", "FlatMod", "FlatMod.esp"))).toBe(true);
    });

    it("flattens single-wrapper subdir without a Data/ name (e.g. <ModName>/plugin.esp)", async () => {
      const { root, ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(join(dest, "WrappedMod_v1.2"), { recursive: true });
            await writeFile(
              join(dest, "WrappedMod_v1.2", "WrappedMod.esp"),
              "fake",
              "utf8",
            );
            return { files: ["WrappedMod_v1.2/WrappedMod.esp"], file_count: 1, dest, format: "zip" };
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
        { mode: "plan", archive_path: "/tmp/wrapped.zip", mod_name: "WrappedMod" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean };
      expect(apply.ok).toBe(true);
      expect(existsSync(join(root, "mods", "WrappedMod", "WrappedMod.esp"))).toBe(true);
      expect(existsSync(join(root, "mods", "WrappedMod", "WrappedMod_v1.2"))).toBe(false);
    });

    it("flattens asset-only mod (textures/ at Data/ wrapper, no plugin)", async () => {
      const { root, ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(join(dest, "Data", "textures"), { recursive: true });
            await writeFile(
              join(dest, "Data", "textures", "diffuse.dds"),
              Buffer.from("DDS "),
              "utf8",
            );
            return { files: ["Data/textures/diffuse.dds"], file_count: 1, dest, format: "zip" };
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
        { mode: "plan", archive_path: "/tmp/textures.zip", mod_name: "TexMod" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean; result: { plugins_registered: string[] } };
      expect(apply.ok).toBe(true);
      // textures/ at root, no Data/ wrapper survives.
      expect(existsSync(join(root, "mods", "TexMod", "textures", "diffuse.dds"))).toBe(true);
      expect(existsSync(join(root, "mods", "TexMod", "Data"))).toBe(false);
      // No plugins to register for an asset-only mod.
      expect(apply.result.plugins_registered).toEqual([]);
    });

    it("BUG-E: plugins.txt is written with the asterisk-enabled prefix and persisted", async () => {
      const { root, ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(dest, { recursive: true });
            await writeFile(join(dest, "RegisterMe.esp"), "fake", "utf8");
            return { files: ["RegisterMe.esp"], file_count: 1, dest, format: "zip" };
          }
          if (method === "world.invalidate") return { invalidated: true };
          throw new Error(`unmocked: ${method}`);
        },
        isReady: () => true,
        start: async () => {},
        stop: async () => {},
      }));
      // Seed plugins.txt with an existing comment + plugin so we can prove
      // the new line was appended (not overwriting existing content).
      await writeFile(
        join(ctx.config.mo2Root, "profiles", "Default", "plugins.txt"),
        "# existing comment\n*ExistingPlugin.esp\n",
        "utf8",
      );

      const tool = getTool("mo2_install")!;
      const plan = (await tool.handler(
        { mode: "plan", archive_path: "/tmp/reg.zip", mod_name: "RegisterMeMod" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean; result: { plugins_registered: string[] } };

      expect(apply.ok).toBe(true);
      expect(apply.result.plugins_registered).toEqual(["RegisterMe.esp"]);
      const pluginsTxt = await readFile(
        join(root, "profiles", "Default", "plugins.txt"),
        "utf8",
      );
      // Pre-existing content preserved.
      expect(pluginsTxt).toContain("# existing comment");
      expect(pluginsTxt).toContain("*ExistingPlugin.esp");
      // New plugin appended with the FO4/SSE asterisk-enabled prefix.
      expect(pluginsTxt).toContain("*RegisterMe.esp");
    });

    it("BUG-E: live broker path calls organizer.refresh after writing plugins.txt", async () => {
      const { root, ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(dest, { recursive: true });
            await writeFile(join(dest, "LivePlugin.esp"), "fake", "utf8");
            return { files: ["LivePlugin.esp"], file_count: 1, dest, format: "zip" };
          }
          if (method === "world.invalidate") return { invalidated: true };
          throw new Error(`unmocked: ${method}`);
        },
        isReady: () => true,
        start: async () => {},
        stop: async () => {},
      }));
      const brokerCalls: string[] = [];
      ctx.pipeClient = {
        call: async (method: string) => {
          brokerCalls.push(method);
          if (method === "profile.active")
            return { ok: true, result: { name: "Default" }, error: null };
          if (method === "installation.create_mod_from_directory") {
            const absolutePath = join(root, "mods", "LivePluginMod");
            await mkdir(absolutePath, { recursive: true });
            return { ok: true, result: { name: "LivePluginMod", absolute_path: absolutePath }, error: null };
          }
          if (method === "organizer.refresh")
            return { ok: true, result: { refreshed: true }, error: null };
          throw new Error(`unmocked broker: ${method}`);
        },
        close: () => {},
        discoverAndConnect: async () => {},
        isConnected: () => true,
      } as unknown as ToolContext["pipeClient"];

      const tool = getTool("mo2_install")!;
      const plan = (await tool.handler(
        { mode: "plan", archive_path: "/tmp/live.zip", mod_name: "LivePluginMod" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const apply = (await tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      )) as { ok: boolean; result: { plugins_registered: string[] } };

      expect(apply.ok).toBe(true);
      expect(apply.result.plugins_registered).toEqual(["LivePlugin.esp"]);
      // organizer.refresh fired after plugins.txt was rewritten so MO2's
      // in-memory plugin list re-reads the file.
      expect(brokerCalls).toContain("organizer.refresh");
    });
  });

  // BUG-14 BUG-F regression (issue #14): plan-only operations must be
  // reentrant for distinct mod_name targets even though they share the
  // same profile's modlist.txt / plugins.txt lease surface. Before the
  // fix, two parallel plans for different mods triggered:
  //   {ok:false, error:{code:"lease_held", message:"Target is already
  //    locked by mo2_install in MCP process N"}}
  // for the second+ plan. Now plan is reentrant; apply serializes.
  describe("BUG-14 BUG-F: parallel plans for distinct mod_names are reentrant", () => {
    it("two parallel plans for different mod_names both succeed", async () => {
      const { ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(dest, { recursive: true });
            await writeFile(join(dest, "x.esp"), "fake", "utf8");
            return { files: ["x.esp"], file_count: 1, dest, format: "zip" };
          }
          if (method === "world.invalidate") return { invalidated: true };
          throw new Error(`unmocked: ${method}`);
        },
        isReady: () => true,
        start: async () => {},
        stop: async () => {},
      }));

      const tool = getTool("mo2_install")!;
      const [plan1, plan2, plan3] = (await Promise.all([
        tool.handler(
          { mode: "plan", archive_path: "/tmp/a.zip", mod_name: "ParallelA" },
          ctx,
        ),
        tool.handler(
          { mode: "plan", archive_path: "/tmp/b.zip", mod_name: "ParallelB" },
          ctx,
        ),
        tool.handler(
          { mode: "plan", archive_path: "/tmp/c.zip", mod_name: "ParallelC" },
          ctx,
        ),
      ])) as Array<{ ok: boolean; result?: unknown; error?: { code: string } }>;

      // Pre-fix: plan2 and plan3 would have returned ok:false / lease_held.
      expect(plan1.ok, `plan1 failed: ${JSON.stringify(plan1.error)}`).toBe(true);
      expect(plan2.ok, `plan2 failed: ${JSON.stringify(plan2.error)}`).toBe(true);
      expect(plan3.ok, `plan3 failed: ${JSON.stringify(plan3.error)}`).toBe(true);
    });

    it("apply still serializes via apply-time lock acquisition", async () => {
      const { ctx } = await _fixture((_root) => ({
        call: async (method, params) => {
          if (method === "fomod.parse_choices") throw new Error("not_a_fomod");
          if (method === "archive.extract_all") {
            const dest = (params as { dest: string }).dest;
            await mkdir(dest, { recursive: true });
            await writeFile(join(dest, "ser.esp"), "fake", "utf8");
            return { files: ["ser.esp"], file_count: 1, dest, format: "zip" };
          }
          if (method === "world.invalidate") return { invalidated: true };
          throw new Error(`unmocked: ${method}`);
        },
        isReady: () => true,
        start: async () => {},
        stop: async () => {},
      }));

      const tool = getTool("mo2_install")!;
      const plan1 = (await tool.handler(
        { mode: "plan", archive_path: "/tmp/s1.zip", mod_name: "SerialA" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      const plan2 = (await tool.handler(
        { mode: "plan", archive_path: "/tmp/s2.zip", mod_name: "SerialB" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };
      expect(plan1.ok).toBe(true);
      expect(plan2.ok).toBe(true);

      // First apply succeeds + mutates modlist.txt + plugins.txt.
      const apply1 = (await tool.handler(
        { mode: "apply", plan_id: plan1.result.planId, lease_token: plan1.result.lease_token },
        ctx,
      )) as { ok: boolean };
      expect(apply1.ok).toBe(true);

      // Second apply: plugins.txt + modlist.txt have drifted since plan2
      // was generated. The apply-time lock acquires successfully (no other
      // lock holder), but verifyLease detects the drift and returns
      // lease_violation. Caller re-plans.
      const apply2 = (await tool.handler(
        { mode: "apply", plan_id: plan2.result.planId, lease_token: plan2.result.lease_token },
        ctx,
      )) as { ok: boolean; error?: { code: string } };
      expect(apply2.ok).toBe(false);
      expect(apply2.error?.code).toBe("lease_violation");
    });
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
