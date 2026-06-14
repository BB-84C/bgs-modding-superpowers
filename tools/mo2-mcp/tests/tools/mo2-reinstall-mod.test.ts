import { describe, it, expect, beforeAll, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

interface MockPipeCall {
  method: string;
  params: Record<string, unknown>;
}

interface MockSidecarCall {
  method: string;
  params: unknown;
}

const roots: string[] = [];

async function fixture(options: { withPipe?: boolean; installFile?: string; createArchive?: boolean } = {}): Promise<{
  root: string;
  ctx: ToolContext;
  pipeCalls: MockPipeCall[];
}> {
  const root = await mkdtemp(join(tmpdir(), "mo2-reinstall-"));
  roots.push(root);
  await mkdir(join(root, "mods", "InstalledMod"), { recursive: true });
  await writeFile(join(root, "mods", "InstalledMod", "file.txt"), "payload", "utf8");
  await mkdir(join(root, "downloads"), { recursive: true });
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+InstalledMod\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\n[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  const installFile = options.installFile ?? "InstalledMod.7z";
  if (options.createArchive) {
    await writeFile(join(root, "downloads", installFile), "archive", "utf8");
  }

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

  const pipeCalls: MockPipeCall[] = [];
  if (options.withPipe) {
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        if (method === "mods.meta_read") {
          return {
            ok: true,
            result: { name: params.name, meta: { General: { installationFile: installFile } }, exists: true },
          };
        }
        if (method === "installation.install_local_archive") {
          return { ok: true, result: { name: params.name_suggestion, installation_file: params.archive_path } };
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

describe("mo2_reinstall_mod", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-reinstall-mod.js");
  });

  afterEach(async () => {
    await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
  });

  it("plan throws live_mo2_required_for_reinstall without pipeClient", async () => {
    const { ctx } = await fixture({ withPipe: false });
    const tool = getTool("mo2_reinstall_mod")!;

    await expect(tool.handler({ mode: "plan", name: "InstalledMod" }, ctx))
      .rejects.toThrow(/live_mo2_required_for_reinstall/);
  });

  it("plan throws no_installation_file_in_meta_ini when meta lacks installationFile", async () => {
    const { ctx } = await fixture({ withPipe: true, createArchive: true });
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        if (method === "mods.meta_read") return { ok: true, result: { name: params.name, meta: {}, exists: true } };
        throw new Error(`unmocked: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_reinstall_mod")!;

    await expect(tool.handler({ mode: "plan", name: "InstalledMod" }, ctx))
      .rejects.toThrow(/no_installation_file_in_meta_ini/);
  });

  it("plan throws archive_not_in_downloads when installationFile is absent from downloads", async () => {
    const { ctx } = await fixture({ withPipe: true, createArchive: false });
    const tool = getTool("mo2_reinstall_mod")!;

    await expect(tool.handler({ mode: "plan", name: "InstalledMod" }, ctx))
      .rejects.toThrow(/archive_not_in_downloads: InstalledMod\.7z/);
  });

  it("apply simple archive calls installation.install_local_archive with archive_path and name_suggestion", async () => {
    const { root, ctx, pipeCalls } = await fixture({ withPipe: true, createArchive: true });
    const sidecarCalls: MockSidecarCall[] = [];
    ctx.sidecar = {
      call: async (method: string, params: unknown) => {
        sidecarCalls.push({ method, params });
        if (method === "fomod.parse_choices") throw new Error("not_a_fomod: no info.xml");
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_reinstall_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "InstalledMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { reinstalled: string; archive: string; fomod_used: boolean } };

    expect(apply.ok).toBe(true);
    expect(apply.result).toMatchObject({ reinstalled: "InstalledMod", archive: "InstalledMod.7z", fomod_used: false });
    expect(pipeCalls).toContainEqual({
      method: "installation.install_local_archive",
      params: { archive_path: join(root, "downloads", "InstalledMod.7z"), name_suggestion: "InstalledMod" },
    });
    expect(sidecarCalls).toContainEqual({ method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } });
  });

  it("apply FOMOD without choices throws fomod_choices_required_for_reinstall", async () => {
    const { ctx } = await fixture({ withPipe: true, createArchive: true });
    ctx.sidecar = {
      call: async (method: string) => {
        if (method === "fomod.parse_choices") return { pages: [{ name: "Install" }] };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_reinstall_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "InstalledMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    await expect(tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )).rejects.toThrow(/fomod_choices_required_for_reinstall/);
  });

  it("apply FOMOD with choices succeeds and returns fomod_used true", async () => {
    const { ctx } = await fixture({ withPipe: true, createArchive: true });
    ctx.sidecar = {
      call: async (method: string) => {
        if (method === "fomod.parse_choices") return { pages: [{ name: "Install" }] };
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_reinstall_mod")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        name: "InstalledMod",
        fomod_choices: [{ page_name: "Install", selected_options: [{ group_name: "G", option_name: "A" }] }],
      },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { fomod_used: boolean } };

    expect(apply.ok).toBe(true);
    expect(apply.result.fomod_used).toBe(true);
  });
});
