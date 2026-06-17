import { describe, it, expect, beforeAll, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
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

async function fixture(options: {
  withPipe?: boolean;
  installFile?: string;
  createArchive?: boolean;
  /**
   * When set, write the archive (createArchive=true) at this absolute path
   * INSTEAD of under <root>/downloads/, and set meta.ini installationFile to
   * this absolute path. Used to exercise BUG-22 absolute-path resolution.
   */
  absoluteArchive?: string;
} = {}): Promise<{
  root: string;
  ctx: ToolContext;
  pipeCalls: MockPipeCall[];
}> {
  const root = await mkdtemp(join(tmpdir(), "mo2-reinstall-"));
  roots.push(root);
  await mkdir(join(root, "mods", "InstalledMod"), { recursive: true });
  await writeFile(join(root, "mods", "InstalledMod", "file.txt"), "payload", "utf8");
  // Existing meta.ini so BUG-23 manual-replacement path can preserve+restore it.
  await writeFile(
    join(root, "mods", "InstalledMod", "meta.ini"),
    "[General]\ngameName=Fallout 4\ninstallationFile=InstalledMod.7z\nversion=1.0\n",
    "utf8",
  );
  await mkdir(join(root, "downloads"), { recursive: true });
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+InstalledMod\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\n[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  const installFile = options.absoluteArchive ?? options.installFile ?? "InstalledMod.7z";
  if (options.createArchive) {
    if (options.absoluteArchive) {
      // Path includes its own parent dirs — make sure they exist before write.
      const parent = options.absoluteArchive.replace(/[\\/][^\\/]+$/, "");
      if (parent && parent !== options.absoluteArchive) {
        await mkdir(parent, { recursive: true });
      }
      await writeFile(options.absoluteArchive, "archive", "utf8");
    } else {
      await writeFile(join(root, "downloads", installFile), "archive", "utf8");
    }
  }

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

  // BUG-22 regression: existing behavior path (basename installationFile) still
  // resolves correctly under <mo2Root>/downloads/. Regression guard for the
  // path.isAbsolute branch.
  it("BUG-22: plan with relative installationFile resolves under <root>/downloads/", async () => {
    const { root, ctx } = await fixture({ withPipe: true, createArchive: true });
    const tool = getTool("mo2_reinstall_mod")!;

    const plan = (await tool.handler({ mode: "plan", name: "InstalledMod" }, ctx)) as {
      ok: boolean;
      result: { diff: string };
    };
    expect(plan.ok).toBe(true);
    // Diff embeds the resolved absolute archivePath; assert it matches downloads/.
    expect(plan.result.diff).toContain(join(root, "downloads", "InstalledMod.7z"));
  });

  // BUG-22 fix: absolute installationFile values (legitimate when MO2 indexes an
  // archive from outside the downloads tree) used to be mangled by path.join into
  // garbage like `C:\downloads\F:\path\to.7z` and trigger a false
  // archive_not_in_downloads error. Now path.isAbsolute-gated.
  it("BUG-22: plan with absolute installationFile resolves to the absolute path verbatim", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-reinstall-abs-"));
    roots.push(root);
    const absArchive = join(root, "external-stash", "Unique NPCs - FOMOD 2.0-21248-2-0.7z");
    const { root: mo2Root, ctx } = await fixture({
      withPipe: true,
      createArchive: true,
      absoluteArchive: absArchive,
    });
    const tool = getTool("mo2_reinstall_mod")!;

    const plan = (await tool.handler({ mode: "plan", name: "InstalledMod" }, ctx)) as {
      ok: boolean;
      result: { diff: string };
    };
    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain(absArchive);
    // Negative: must NOT be the path.join-concatenated garbage form.
    expect(plan.result.diff).not.toContain(join(mo2Root, "downloads", absArchive));
  });

  it("plan throws archive_missing when installationFile is absent (relative)", async () => {
    const { ctx } = await fixture({ withPipe: true, createArchive: false });
    const tool = getTool("mo2_reinstall_mod")!;

    await expect(tool.handler({ mode: "plan", name: "InstalledMod" }, ctx))
      .rejects.toThrow(/archive_missing:.*InstalledMod\.7z/);
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
    expect(pipeCalls.some((call) => call.method === "organizer.refresh")).toBe(false);
    expect(sidecarCalls).toContainEqual({ method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } });
    // Non-FOMOD must NOT route through stage_fomod (regression guard for BUG-23).
    expect(sidecarCalls.some((call) => call.method === "install.stage_fomod")).toBe(false);
  });

  // BUG-24 fix: FOMOD detection + tree surfacing now happens at plan time
  // (was apply time before). Mirrors mo2_install's fomod_choices_required
  // shape. Includes the parsed FOMOD tree on the thrown error so the agent
  // can introspect pages/groups/options before retrying with choices.
  it("BUG-24: plan throws fomod_choices_required_for_reinstall with FOMOD tree when archive is FOMOD and no choices given", async () => {
    const { ctx } = await fixture({ withPipe: true, createArchive: true });
    const fakeTree = {
      fomod_name: "InstalledMod",
      pages: [{ name: "Pick variant", groups: [{ name: "Variant", type: "SelectExactlyOne", options: [{ name: "A", type: "Optional" }, { name: "B", type: "Optional" }] }] }],
    };
    ctx.sidecar = {
      call: async (method: string) => {
        if (method === "fomod.parse_choices") return fakeTree;
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_reinstall_mod")!;

    // The error message must match; the fomod_tree property must be attached.
    let caught: unknown = undefined;
    try {
      await tool.handler({ mode: "plan", name: "InstalledMod" }, ctx);
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(Error);
    expect((caught as Error).message).toMatch(/fomod_choices_required_for_reinstall/);
    expect((caught as Error & { fomod_tree?: unknown }).fomod_tree).toEqual(fakeTree);
  });

  // BUG-23 fix: FOMOD apply now routes through sidecar install.stage_fomod
  // (Pattern A) and replaces the existing mod folder content manually. The
  // broker's FOMOD-blind installMod primitive must NEVER be called on a FOMOD
  // archive (it would popup the MO2 native FOMOD wizard and block the Qt main
  // thread).
  it("BUG-23: apply FOMOD with choices routes through install.stage_fomod and replaces mod content (NOT install_local_archive)", async () => {
    const { root, ctx, pipeCalls } = await fixture({ withPipe: true, createArchive: true });
    const sidecarCalls: MockSidecarCall[] = [];
    ctx.sidecar = {
      call: async (method: string, params: unknown) => {
        sidecarCalls.push({ method, params });
        if (method === "fomod.parse_choices") return { pages: [{ name: "Install" }] };
        if (method === "install.stage_fomod") {
          // Simulate sidecar staging: create the staging_dir and write a few files
          // that should end up in the mod folder.
          const p = params as { staging_dir: string };
          await mkdir(join(p.staging_dir, "meshes"), { recursive: true });
          await writeFile(join(p.staging_dir, "meshes", "newmesh.nif"), "staged-nif-content", "utf8");
          await writeFile(join(p.staging_dir, "readme.txt"), "staged readme", "utf8");
          return { staging_dir: p.staging_dir, file_count: 2, files: [], archive_format: "7z" };
        }
        if (method === "world.invalidate") return { invalidated: true };
        throw new Error(`unmocked: ${method}`);
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];

    const tool = getTool("mo2_reinstall_mod")!;
    const choices = [{ page_name: "Install", selected_options: [{ group_name: "G", option_name: "A" }] }];
    const plan = (await tool.handler(
      { mode: "plan", name: "InstalledMod", fomod_choices: choices },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { reinstalled: string; archive: string; fomod_used: boolean } };

    expect(apply.ok).toBe(true);
    expect(apply.result).toMatchObject({ reinstalled: "InstalledMod", archive: "InstalledMod.7z", fomod_used: true });

    // Pattern A: sidecar staging must have been called with the choices.
    const stageCall = sidecarCalls.find((c) => c.method === "install.stage_fomod");
    expect(stageCall).toBeDefined();
    expect((stageCall!.params as { choices: unknown }).choices).toEqual(choices);
    expect((stageCall!.params as { archive_path: string }).archive_path).toBe(join(root, "downloads", "InstalledMod.7z"));

    // BUG-23 critical assertion: the broker's FOMOD-blind primitive must NEVER
    // be called for a FOMOD archive. This is the regression guard that
    // prevents BUG-16-class Qt main-thread modal hangs.
    expect(pipeCalls.some((c) => c.method === "installation.install_local_archive")).toBe(false);

    // Memory rule 45-2: TS layer must NEVER call broker organizer.refresh.
    expect(pipeCalls.some((c) => c.method === "organizer.refresh")).toBe(false);

    // World cache invalidation still happens so subsequent asset reads see the
    // new content.
    expect(sidecarCalls).toContainEqual({ method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } });

    // Semantic readback: staged content actually landed in the mod folder.
    const modPath = join(root, "mods", "InstalledMod");
    expect(existsSync(join(modPath, "meshes", "newmesh.nif"))).toBe(true);
    expect(existsSync(join(modPath, "readme.txt"))).toBe(true);
    // Old content was wiped.
    expect(existsSync(join(modPath, "file.txt"))).toBe(false);
    // meta.ini was preserved + updated with new installationFile.
    const metaAfter = await readFile(join(modPath, "meta.ini"), "utf8");
    expect(metaAfter).toContain("gameName=Fallout 4");
    expect(metaAfter).toMatch(/installationFile=InstalledMod\.7z/);
    // Staging dir was cleaned up.
    const stagingDirArg = (stageCall!.params as { staging_dir: string }).staging_dir;
    expect(existsSync(stagingDirArg)).toBe(false);
  });

  // BUG-24 + BUG-23 interaction: when a FOMOD archive has no choices supplied,
  // plan time is the gate. The defensive apply-time gate stays as a safety
  // net, but the agent should never reach it through plan-then-apply.
  it("BUG-24: plan-time gate fires before apply for FOMOD without choices", async () => {
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

    // Plan-time throw — no apply call needed.
    await expect(tool.handler({ mode: "plan", name: "InstalledMod" }, ctx))
      .rejects.toThrow(/fomod_choices_required_for_reinstall/);
  });
});
