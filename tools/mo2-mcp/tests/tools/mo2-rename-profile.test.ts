import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

const detectMo2RunningMock = vi.hoisted(() => vi.fn());

vi.mock("../../src/detection.js", () => ({
  detectMo2Running: detectMo2RunningMock,
}));

const roots: string[] = [];

async function fixture(options: { selectedLine?: string; targetExists?: boolean; oldExists?: boolean } = {}): Promise<{
  root: string;
  ctx: ToolContext;
  iniText: string;
}> {
  const root = await mkdtemp(join(tmpdir(), "mo2-rename-profile-"));
  roots.push(root);
  await mkdir(join(root, "profiles"), { recursive: true });
  if (options.oldExists ?? true) {
    await mkdir(join(root, "profiles", "Default"), { recursive: true });
    await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+BaseMod\n", "utf8");
  }
  if (options.targetExists) {
    await mkdir(join(root, "profiles", "Renamed"), { recursive: true });
  }
  const selectedLine = options.selectedLine ?? "selected_profile=Other";
  const iniText = [
    "[General]",
    "gameName=Fallout 4",
    selectedLine,
    "gamePath=C:/Games/Fallout 4",
    "version=2.5.3",
    "",
    "[Settings]",
    "language=en",
    "",
  ].join("\n");
  await writeFile(join(root, "ModOrganizer.ini"), iniText, "utf8");

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
  return { root, ctx, iniText };
}

describe("mo2_rename_profile", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-rename-profile.js");
  });

  beforeEach(() => {
    detectMo2RunningMock.mockResolvedValue({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
  });

  afterEach(async () => {
    await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
    vi.clearAllMocks();
  });

  it("plan throws mo2_running when MO2 process is detected", async () => {
    detectMo2RunningMock.mockResolvedValueOnce({
      processRunning: true,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
    const { ctx } = await fixture({ selectedLine: "selected_profile=Default" });
    const tool = getTool("mo2_rename_profile")!;

    await expect(tool.handler({ mode: "plan", old_name: "Default", new_name: "Renamed" }, ctx))
      .rejects.toThrow(/mo2_running: close MO2 before renaming profile/);
  });

  it("plan validates source and target profile directories", async () => {
    const missing = await fixture({ oldExists: false });
    const existingTarget = await fixture({ targetExists: true });
    const tool = getTool("mo2_rename_profile")!;

    await expect(tool.handler({ mode: "plan", old_name: "Default", new_name: "Renamed" }, missing.ctx))
      .rejects.toThrow(/profile_not_found/);
    await expect(tool.handler({ mode: "plan", old_name: "Default", new_name: "Renamed" }, existingTarget.ctx))
      .rejects.toThrow(/target_exists/);
  });

  it("plan diff and affected files reflect whether selected_profile matches", async () => {
    const matching = await fixture({ selectedLine: "selected_profile=@ByteArray(Default)" });
    const notMatching = await fixture({ selectedLine: "selected_profile=Other" });
    const tool = getTool("mo2_rename_profile")!;

    const updatePlan = (await tool.handler(
      { mode: "plan", old_name: "Default", new_name: "Renamed" },
      matching.ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };
    const noUpdatePlan = (await tool.handler(
      { mode: "plan", old_name: "Default", new_name: "Renamed" },
      notMatching.ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };

    expect(updatePlan.result.diff).toBe("Rename profile dir + update ModOrganizer.ini selected_profile");
    expect(updatePlan.result.affected_files).toEqual([
      join(matching.root, "profiles", "Renamed"),
      join(matching.root, "ModOrganizer.ini"),
    ]);
    expect(noUpdatePlan.result.diff).toBe("Rename profile dir + no ini update");
    expect(noUpdatePlan.result.affected_files).toEqual([join(notMatching.root, "profiles", "Renamed")]);
  });

  it("apply renames profile dir and rewrites plain selected_profile line only", async () => {
    const local = await fixture({ selectedLine: "selected_profile=Default" });
    const tool = getTool("mo2_rename_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", old_name: "Default", new_name: "Renamed" },
      local.ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      local.ctx,
    )) as { ok: boolean; result: { renamed: boolean; ini_updated: boolean } };
    const ini = await readFile(join(local.root, "ModOrganizer.ini"), "utf8");

    expect(apply.result).toMatchObject({ renamed: true, ini_updated: true });
    expect(existsSync(join(local.root, "profiles", "Default"))).toBe(false);
    expect(existsSync(join(local.root, "profiles", "Renamed", "modlist.txt"))).toBe(true);
    expect(ini).toContain("selected_profile=Renamed");
    expect(ini).toContain("gameName=Fallout 4\nselected_profile=Renamed\ngamePath=C:/Games/Fallout 4");
  });

  it("apply preserves actual MO2 @ByteArray selected_profile wrapper", async () => {
    const { root, ctx } = await fixture({ selectedLine: "selected_profile=@ByteArray(Default)" });
    const tool = getTool("mo2_rename_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", old_name: "Default", new_name: "Renamed" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    ) as { ok: boolean; result: { ini_updated: boolean } };

    const ini = await readFile(join(root, "ModOrganizer.ini"), "utf8");
    expect(apply.result.ini_updated).toBe(true);
    expect(ini).toContain("selected_profile=@ByteArray(Renamed)");
    expect(ini).toContain("version=2.5.3\n\n[Settings]\nlanguage=en");
  });

  it("apply without matching selected_profile leaves ini byte-for-byte untouched", async () => {
    const { root, ctx, iniText } = await fixture({ selectedLine: "selected_profile=Other" });
    const tool = getTool("mo2_rename_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", old_name: "Default", new_name: "Renamed" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { renamed: boolean; ini_updated: boolean } };

    expect(apply.result.ini_updated).toBe(false);
    expect(await readFile(join(root, "ModOrganizer.ini"), "utf8")).toBe(iniText);
    expect(existsSync(join(root, "profiles", "Renamed", "modlist.txt"))).toBe(true);
  });
});
