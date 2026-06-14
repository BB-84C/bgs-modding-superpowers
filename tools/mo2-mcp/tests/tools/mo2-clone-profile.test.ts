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

async function fixture(options: { source?: boolean; target?: boolean } = {}): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-clone-profile-"));
  roots.push(root);
  const profilesRoot = join(root, "profiles");
  await mkdir(profilesRoot, { recursive: true });

  if (options.source ?? true) {
    const src = join(profilesRoot, "Default");
    await mkdir(join(src, "saves"), { recursive: true });
    await mkdir(join(src, "logs"), { recursive: true });
    await mkdir(join(src, "crashDumps"), { recursive: true });
    await mkdir(join(src, "nested"), { recursive: true });
    await writeFile(join(src, "modlist.txt"), "+BaseMod\n", "utf8");
    await writeFile(join(src, "plugins.txt"), "*Fallout4.esm\n", "utf8");
    await writeFile(join(src, "nested", "profile.ini"), "[profile]\n", "utf8");
    await writeFile(join(src, "saves", "save.fos"), "save", "utf8");
    await writeFile(join(src, "logs", "mo_interface.log"), "log", "utf8");
    await writeFile(join(src, "crashDumps", "dump.dmp"), "dump", "utf8");
    await writeFile(join(src, "transient.bak"), "bak", "utf8");
  }

  if (options.target) {
    await mkdir(join(profilesRoot, "Clone"), { recursive: true });
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

  return { root, ctx };
}

describe("mo2_clone_profile", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-clone-profile.js");
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
    const { ctx } = await fixture();
    const tool = getTool("mo2_clone_profile")!;

    await expect(tool.handler({ mode: "plan", source: "Default", target: "Clone" }, ctx))
      .rejects.toThrow(/mo2_running: close MO2 before cloning profile/);
  });

  it("plan validates source existence and target nonexistence", async () => {
    const missingSource = await fixture({ source: false });
    const existingTarget = await fixture({ target: true });
    const tool = getTool("mo2_clone_profile")!;

    await expect(tool.handler({ mode: "plan", source: "Default", target: "Clone" }, missingSource.ctx))
      .rejects.toThrow(/source_profile_not_found/);
    await expect(tool.handler({ mode: "plan", source: "Default", target: "Clone" }, existingTarget.ctx))
      .rejects.toThrow(/target_profile_exists/);
  });

  it("apply default clone skips saves, logs, crashDumps, and .bak files", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_clone_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", source: "Default", target: "Clone" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string; diff: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { cloned_from: string; to: string; dst_path: string } };

    expect(plan.result.diff).toBe("Clone profile Default → Clone (include_saves=false)");
    expect(apply.result).toMatchObject({ cloned_from: "Default", to: "Clone", dst_path: join(root, "profiles", "Clone") });
    expect(await readFile(join(root, "profiles", "Clone", "modlist.txt"), "utf8")).toBe("+BaseMod\n");
    expect(await readFile(join(root, "profiles", "Clone", "plugins.txt"), "utf8")).toBe("*Fallout4.esm\n");
    expect(await readFile(join(root, "profiles", "Clone", "nested", "profile.ini"), "utf8")).toBe("[profile]\n");
    expect(existsSync(join(root, "profiles", "Clone", "saves"))).toBe(false);
    expect(existsSync(join(root, "profiles", "Clone", "logs"))).toBe(false);
    expect(existsSync(join(root, "profiles", "Clone", "crashDumps"))).toBe(false);
    expect(existsSync(join(root, "profiles", "Clone", "transient.bak"))).toBe(false);
  });

  it("apply include_saves true copies saves while still skipping logs, crashDumps, and .bak", async () => {
    const { root, ctx } = await fixture();
    const tool = getTool("mo2_clone_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", source: "Default", target: "Clone", include_saves: true },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string; diff: string } };

    const apply = await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    ) as { ok: boolean };

    expect(apply.ok).toBe(true);
    expect(plan.result.diff).toBe("Clone profile Default → Clone (include_saves=true)");
    expect(await readFile(join(root, "profiles", "Clone", "saves", "save.fos"), "utf8")).toBe("save");
    expect(existsSync(join(root, "profiles", "Clone", "logs"))).toBe(false);
    expect(existsSync(join(root, "profiles", "Clone", "crashDumps"))).toBe(false);
    expect(existsSync(join(root, "profiles", "Clone", "transient.bak"))).toBe(false);
  });
});
