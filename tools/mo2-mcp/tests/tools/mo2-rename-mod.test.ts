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

async function _fixture(withPipe = false): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-rename-"));
  await mkdir(join(root, "mods", "OldMod"), { recursive: true });
  await writeFile(join(root, "mods", "OldMod", "file.txt"), "payload", "utf8");
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await mkdir(join(root, "profiles", "Alt"), { recursive: true });
  await mkdir(join(root, "profiles", "Other"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+OldMod\n+Keep\n", "utf8");
  await writeFile(join(root, "profiles", "Alt", "modlist.txt"), "-OldMod\n+Keep\n", "utf8");
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
      permissionCeiling: "metadata-editable",
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
  if (withPipe) {
    ctx.pipeClient = {
      call: async () => ({ ok: true, result: { old_name: "OldMod", new_name: "NewMod" } }),
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
  }
  return { root, ctx };
}

describe("mo2_rename_mod", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-rename-mod.js");
  });

  it("plan scans all profiles and includes the old mod directory as a target", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_rename_mod")!;

    const plan = (await tool.handler(
      { mode: "plan", old_name: "OldMod", new_name: "NewMod" },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[]; planId: string } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("across 2 profiles + mod dir");
    expect(plan.result.affected_files.sort()).toEqual([
      join(root, "profiles", "Alt", "modlist.txt"),
      join(root, "profiles", "Default", "modlist.txt"),
    ].sort());
    const rec = ctx.plans.get(plan.result.planId)!;
    expect(rec.lease.components.map((component) => component.path)).toContain(join(root, "mods", "OldMod"));
  });

  it("apply live refreshes before mods.rename, then refreshes and invalidates sidecar", async () => {
    const { root, ctx } = await _fixture(true);
    const pipeCalls: Array<{ method: string; params: Record<string, unknown> }> = [];
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        return { ok: true, result: { old_name: params.old_name, new_name: params.new_name } };
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const sidecarCalls: Array<{ method: string; params: unknown }> = [];
    ctx.sidecar = {
      call: async (method: string, params: unknown) => {
        sidecarCalls.push({ method, params });
        return { invalidated: true };
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_rename_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", old_name: "OldMod", new_name: "NewMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { old_name: string; new_name: string } };

    expect(apply.ok).toBe(true);
    expect(pipeCalls).toEqual([
      { method: "organizer.refresh", params: { save_changes: false } },
      { method: "mods.rename", params: { old_name: "OldMod", new_name: "NewMod" } },
      { method: "organizer.refresh", params: { save_changes: false } },
    ]);
    expect(sidecarCalls).toEqual([
      { method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Alt") } },
      { method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } },
    ]);
  });

  it("apply offline renames directory and rewrites matching profiles only", async () => {
    const { root, ctx } = await _fixture(false);
    const tool = getTool("mo2_rename_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", old_name: "OldMod", new_name: "NewMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { renamed_dir: boolean; profiles_updated: string[] } };

    expect(apply.ok).toBe(true);
    expect(apply.result.renamed_dir).toBe(true);
    expect(apply.result.profiles_updated.sort()).toEqual(["Alt", "Default"]);
    expect(existsSync(join(root, "mods", "OldMod"))).toBe(false);
    expect(existsSync(join(root, "mods", "NewMod", "file.txt"))).toBe(true);
    expect(await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8"))
      .toBe("+NewMod\n+Keep\n");
    expect(await readFile(join(root, "profiles", "Alt", "modlist.txt"), "utf8"))
      .toBe("-NewMod\n+Keep\n");
    expect(await readFile(join(root, "profiles", "Other", "modlist.txt"), "utf8"))
      .toBe("+Different\n");
  });
});
