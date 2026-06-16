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

async function fixture(options: { withPipe?: boolean; resolvedPath?: string | null | ((root: string) => string | null) } = {}): Promise<{
  root: string;
  ctx: ToolContext;
  pipeCalls: Array<{ method: string; params: Record<string, unknown> }>;
}> {
  const root = await mkdtemp(join(tmpdir(), "mo2-hide-"));
  roots.push(root);
  await mkdir(join(root, "mods", "Low", "Data", "textures"), { recursive: true });
  await mkdir(join(root, "mods", "High", "Data", "textures"), { recursive: true });
  await mkdir(join(root, "mods", "Disabled", "Data", "textures"), { recursive: true });
  await writeFile(join(root, "mods", "Low", "Data", "textures", "same.dds"), "low", "utf8");
  await writeFile(join(root, "mods", "High", "Data", "textures", "same.dds"), "high", "utf8");
  await writeFile(join(root, "mods", "Disabled", "Data", "textures", "same.dds"), "disabled", "utf8");
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    ["+High", "-Disabled", "+Low", "+Tools_separator", ""].join("\n"),
    "utf8",
  );
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
    const resolvedPath = typeof options.resolvedPath === "function"
      ? options.resolvedPath(root)
      : options.resolvedPath;
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        if (method === "organizer.resolve_path") {
          return { ok: true, result: { filename: params.filename, resolved: resolvedPath } };
        }
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

describe("mo2_set_file_hidden", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-set-file-hidden.js");
  });

  afterEach(async () => {
    await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
  });

  it("plan live resolves visible file and produces visible-to-hidden diff", async () => {
    const { root, ctx } = await fixture({
      withPipe: true,
      resolvedPath: (fixtureRoot) => join(fixtureRoot, "mods", "High", "Data", "textures", "same.dds"),
    });
    const tool = getTool("mo2_set_file_hidden")!;

    const plan = (await tool.handler(
      { mode: "plan", virtual_path: "Data/textures/same.dds", hidden: true },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("same.dds →");
    expect(plan.result.diff).toContain("same.dds.mohidden");
    expect(plan.result.affected_files).toEqual([
      join(root, "mods", "High", "Data", "textures", "same.dds"),
      join(root, "mods", "High", "Data", "textures", "same.dds.mohidden"),
    ]);
  });

  it("plan live resolves hidden file and produces hidden-to-visible diff", async () => {
    const { root, ctx } = await fixture({
      withPipe: true,
      resolvedPath: (fixtureRoot) => join(fixtureRoot, "mods", "High", "Data", "textures", "same.dds.mohidden"),
    });
    await writeFile(join(root, "mods", "High", "Data", "textures", "same.dds.mohidden"), "hidden", "utf8");
    const tool = getTool("mo2_set_file_hidden")!;

    const plan = (await tool.handler(
      { mode: "plan", virtual_path: "Data/textures/same.dds", hidden: false },
      ctx,
    )) as { ok: boolean; result: { diff: string } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("same.dds.mohidden →");
    expect(plan.result.diff).toContain("same.dds");
  });

  it("plan offline finds the winning enabled mod by priority and throws when missing", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_set_file_hidden")!;

    const plan = (await tool.handler(
      { mode: "plan", virtual_path: "textures/same.dds", hidden: true },
      ctx,
    )) as { ok: boolean; result: { diff: string } };

    expect(plan.result.diff).toContain(join(root, "mods", "High", "Data", "textures", "same.dds"));
    expect(plan.result.diff).not.toContain(join(root, "mods", "Low"));
    await expect(tool.handler(
      { mode: "plan", virtual_path: "textures/missing.dds", hidden: true },
      ctx,
    )).rejects.toThrow(/file_not_found_in_enabled_mods/);
  });

  it("plan no-op reports already hidden when desired hidden state already matches", async () => {
    const { root, ctx } = await fixture();
    await writeFile(join(root, "mods", "High", "Data", "textures", "already.dds.mohidden"), "hidden", "utf8");
    const tool = getTool("mo2_set_file_hidden")!;

    const plan = (await tool.handler(
      { mode: "plan", virtual_path: "textures/already.dds", hidden: true },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toBe("no-op (already hidden)");
    expect(plan.result.affected_files).toEqual([join(root, "mods", "High", "Data", "textures", "already.dds.mohidden")]);
  });

  it("apply renames a fixture file hidden and then visible again", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_set_file_hidden")!;

    const hidePlan = (await tool.handler(
      { mode: "plan", virtual_path: "textures/same.dds", hidden: true },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    const hide = (await tool.handler(
      { mode: "apply", plan_id: hidePlan.result.planId, lease_token: hidePlan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { renamed_from: string; renamed_to: string; hidden: boolean } };

    expect(hide.ok).toBe(true);
    expect(hide.result.hidden).toBe(true);
    expect(existsSync(join(root, "mods", "High", "Data", "textures", "same.dds"))).toBe(false);
    expect(await readFile(join(root, "mods", "High", "Data", "textures", "same.dds.mohidden"), "utf8")).toBe("high");

    const unhidePlan = (await tool.handler(
      { mode: "plan", virtual_path: "textures/same.dds", hidden: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    const unhide = (await tool.handler(
      { mode: "apply", plan_id: unhidePlan.result.planId, lease_token: unhidePlan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { renamed_from: string; renamed_to: string; hidden: boolean } };

    expect(unhide.ok).toBe(true);
    expect(unhide.result.hidden).toBe(false);
    expect(await readFile(join(root, "mods", "High", "Data", "textures", "same.dds"), "utf8")).toBe("high");
  });

  it("apply live invalidates sidecar after hidden-state rename without organizer.refresh", async () => {
    const { root, ctx, pipeCalls } = await fixture({
      withPipe: true,
      resolvedPath: (fixtureRoot) => join(fixtureRoot, "mods", "High", "Data", "textures", "same.dds"),
    });
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
    const tool = getTool("mo2_set_file_hidden")!;
    const plan = (await tool.handler(
      { mode: "plan", virtual_path: "Data/textures/same.dds", hidden: true },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { renamed_from: string; renamed_to: string; hidden: boolean } };

    expect(apply.ok).toBe(true);
    expect(pipeCalls).toEqual([
      { method: "organizer.resolve_path", params: { filename: "Data/textures/same.dds" } },
      { method: "organizer.resolve_path", params: { filename: "Data/textures/same.dds" } },
    ]);
    expect(sidecarCalls).toEqual([
      { method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } },
    ]);
  });

  it("apply no-op returns no_op true without renaming", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_set_file_hidden")!;
    const plan = (await tool.handler(
      { mode: "plan", virtual_path: "textures/same.dds", hidden: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { no_op: boolean; path: string } };

    expect(apply.ok).toBe(true);
    expect(apply.result.no_op).toBe(true);
    expect(apply.result.path).toBe(join(root, "mods", "High", "Data", "textures", "same.dds"));
    expect(existsSync(join(root, "mods", "High", "Data", "textures", "same.dds.mohidden"))).toBe(false);
  });
});
