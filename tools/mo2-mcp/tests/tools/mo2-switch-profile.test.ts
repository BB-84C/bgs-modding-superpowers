import { describe, it, expect, beforeAll, vi } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import { detectMo2Running } from "../../src/detection.js";
import type { ToolContext } from "../../src/types.js";
import type { DetectionResult } from "../../src/detection.js";

const pipeState = vi.hoisted(() => ({
  instances: [] as Array<{
    call: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
    discoverAndConnect: ReturnType<typeof vi.fn>;
    isConnected: ReturnType<typeof vi.fn>;
  }>,
}));

vi.mock("node:child_process", () => ({
  spawn: vi.fn(),
}));

vi.mock("../../src/detection.js", () => ({
  detectMo2Running: vi.fn(),
}));

vi.mock("../../src/pipe-client.js", () => ({
  PipeClient: vi.fn().mockImplementation(() => {
    const client = {
      call: vi.fn(),
      close: vi.fn(),
      discoverAndConnect: vi.fn().mockResolvedValue(undefined),
      isConnected: vi.fn().mockReturnValue(true),
    };
    pipeState.instances.push(client);
    return client;
  }),
}));

function _det(processRunning: boolean, pid?: number): DetectionResult {
  return {
    processRunning,
    pid,
    sharedMemoryPresent: processRunning,
    profileLockHeld: false,
    online: processRunning,
  };
}

async function _fixture(allowedProfiles = ["Default", "ProfileB"]): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-switch-"));
  for (const profile of ["Default", "ProfileB"]) {
    await mkdir(join(root, "profiles", profile), { recursive: true });
    await writeFile(join(root, "profiles", profile, "modlist.txt"), "", "utf8");
    await writeFile(join(root, "profiles", profile, "plugins.txt"), "", "utf8");
  }
  await mkdir(join(root, "mods"), { recursive: true });
  await mkdir(join(root, "plugins", "Mo2AgentControl", "bootstrap", "runtime"), { recursive: true });
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\n[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable",
      allowedProfiles,
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

describe("mo2_switch_profile", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-switch-profile.js");
  });

  it("plan throws profile_not_found when the profile directory is missing", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_switch_profile")!;

    await expect(
      tool.handler({ mode: "plan", new_profile: "Missing" }, ctx),
    ).rejects.toThrow(/profile_not_found: Missing/);
  });

  it("plan throws profile_not_allowed when profile is outside allowedProfiles", async () => {
    const { ctx } = await _fixture(["Default"]);
    const tool = getTool("mo2_switch_profile")!;

    await expect(
      tool.handler({ mode: "plan", new_profile: "ProfileB" }, ctx),
    ).rejects.toThrow(/profile_not_allowed: ProfileB/);
  });

  it("plan returns a non-empty cold-restart diff when profile is valid", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_switch_profile")!;

    const plan = (await tool.handler(
      { mode: "plan", new_profile: "ProfileB" },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("Cold-restart MO2 with -p ProfileB");
    expect(plan.result.affected_files).toEqual([]);
  });

  it("apply follows shutdown, PID-gone, relaunch, endpoint, reconnect, invalidate ladder", async () => {
    vi.useFakeTimers();
    try {
      pipeState.instances.length = 0;
      vi.mocked(detectMo2Running).mockReset();
      vi.mocked(spawn).mockReset();
      const { root, ctx } = await _fixture();
      await writeFile(
        join(root, "plugins", "Mo2AgentControl", "bootstrap", "runtime", "endpoint.json"),
        JSON.stringify({ endpoint: "\\\\.\\pipe\\mo2-new", mo2Pid: 777 }),
        "utf8",
      );
      vi.mocked(detectMo2Running)
        .mockResolvedValueOnce(_det(true, 100))
        .mockResolvedValueOnce(_det(false))
        .mockResolvedValueOnce(_det(true, 777));
      const child = { unref: vi.fn() };
      vi.mocked(spawn).mockReturnValue(child as never);
      const shutdownCalls: Array<{ method: string; timeout?: number }> = [];
      const oldPipe = {
        call: async (method: string, _params: Record<string, unknown>, timeoutMs?: number) => {
          shutdownCalls.push({ method, timeout: timeoutMs });
          return { ok: true, result: { shutting_down: true } };
        },
        close: vi.fn(),
        discoverAndConnect: async () => {},
        isConnected: () => true,
      };
      ctx.pipeClient = oldPipe as unknown as ToolContext["pipeClient"];
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
      const tool = getTool("mo2_switch_profile")!;
      const plan = (await tool.handler(
        { mode: "plan", new_profile: "ProfileB" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };

      const applyPromise = tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      ) as Promise<{ ok: boolean; result: { new_profile: string; new_pipe: string } }>;
      await vi.advanceTimersByTimeAsync(1000);
      const apply = await applyPromise;

      expect(apply.ok).toBe(true);
      expect(apply.result).toMatchObject({ new_profile: "ProfileB", new_pipe: "\\\\.\\pipe\\mo2-new" });
      expect(shutdownCalls).toEqual([{ method: "system.shutdown", timeout: 10000 }]);
      expect(oldPipe.close).toHaveBeenCalledOnce();
      expect(detectMo2Running).toHaveBeenCalledTimes(3);
      expect(spawn).toHaveBeenCalledWith(
        join(root, "ModOrganizer.exe"),
        ["-p", "ProfileB"],
        { detached: true, stdio: "ignore" },
      );
      expect(child.unref).toHaveBeenCalledOnce();
      expect(pipeState.instances[0].discoverAndConnect).toHaveBeenCalledWith(root);
      expect(ctx.pipeClient).toBe(pipeState.instances[0]);
      expect(sidecarCalls).toEqual([
        { method: "world.invalidate", params: { profile_dir: join(root, "profiles", "ProfileB") } },
      ]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("apply throws mo2_shutdown_timeout_30s when MO2 never exits", async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(detectMo2Running).mockReset();
      vi.mocked(detectMo2Running).mockResolvedValue(_det(true, 100));
      const { ctx } = await _fixture();
      ctx.pipeClient = {
        call: async () => ({ ok: true, result: { shutting_down: true } }),
        close: vi.fn(),
        discoverAndConnect: async () => {},
        isConnected: () => true,
      } as unknown as ToolContext["pipeClient"];
      const tool = getTool("mo2_switch_profile")!;
      const plan = (await tool.handler(
        { mode: "plan", new_profile: "ProfileB" },
        ctx,
      )) as { ok: boolean; result: { planId: string; lease_token: string } };

      const applyPromise = tool.handler(
        { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
        ctx,
      );
      const rejection = expect(applyPromise).rejects.toThrow(/mo2_shutdown_timeout_30s/);
      await vi.advanceTimersByTimeAsync(30000);

      await rejection;
      expect(detectMo2Running).toHaveBeenCalledTimes(30);
    } finally {
      vi.useRealTimers();
    }
  });
});
