import { describe, it, expect, beforeAll, vi } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import { readMoIni } from "../../src/mo-ini.js";
import { detectMo2Running } from "../../src/detection.js";
import type { ToolContext } from "../../src/types.js";

vi.mock("../../src/detection.js", () => ({
  detectMo2Running: vi.fn(),
}));

const BASE_INI = [
  "[General]",
  "game=fallout4",
  "selected_profile=Default",
  "",
  "[customExecutables]",
  "size=2",
  "1\\arguments=-FO4",
  "1\\binary=C:/Tools/xEdit/xEdit.exe",
  "1\\hide=false",
  "1\\ownicon=true",
  "1\\steamAppID=",
  "1\\title=xEdit",
  "1\\toolbar=false",
  "1\\workingDirectory=C:/Tools/xEdit",
  "2\\arguments=--game=fallout4",
  "2\\binary=C:/Tools/LOOT/LOOT.exe",
  "2\\hide=false",
  "2\\ownicon=false",
  "2\\steamAppID=",
  "2\\title=LOOT",
  "2\\toolbar=true",
  "2\\workingDirectory=C:/Tools/LOOT",
  "",
  "[Settings]",
  "base_directory=C:/MO2",
  "mod_directory=C:/MO2/mods",
  "",
  "[other]",
  "foo=bar",
  "",
].join("\n");

function _section(text: string, name: string): string {
  const lines = text.split("\n");
  const start = lines.findIndex((line) => line === `[${name}]`);
  if (start < 0) return "";
  const end = lines.findIndex((line, idx) => idx > start && /^\[.+\]$/.test(line));
  return lines.slice(start, end < 0 ? lines.length : end).join("\n");
}

async function _fixture(iniText = BASE_INI): Promise<{ root: string; ctx: ToolContext; iniPath: string }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-exe-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "mods"), { recursive: true });
  const iniPath = join(root, "ModOrganizer.ini");
  await writeFile(iniPath, iniText, "utf8");
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
  return { root, ctx, iniPath };
}

describe("mo2_configure_executable", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-configure-executable.js");
  });

  it("plan throws mo2_running_ini_unsafe when MO2 is running", async () => {
    vi.mocked(detectMo2Running).mockResolvedValueOnce({
      processRunning: true,
      sharedMemoryPresent: true,
      profileLockHeld: false,
      pid: 1,
      online: true,
    });
    const { ctx } = await _fixture();
    const tool = getTool("mo2_configure_executable")!;

    await expect(
      tool.handler({ mode: "plan", action: "remove", title: "xEdit" }, ctx),
    ).rejects.toThrow(/mo2_running_ini_unsafe/);
  });

  it("plan add rejects duplicate title and succeeds with + title diff", async () => {
    vi.mocked(detectMo2Running).mockResolvedValue({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
    const { ctx } = await _fixture();
    const tool = getTool("mo2_configure_executable")!;

    await expect(
      tool.handler(
        { mode: "plan", action: "add", entry: { title: "xEdit", binary: "C:/Other/xEdit.exe" } },
        ctx,
      ),
    ).rejects.toThrow(/title_exists: xEdit/);

    const plan = (await tool.handler(
      { mode: "plan", action: "add", entry: { title: "BethINI", binary: "C:/Tools/BethINI.exe" } },
      ctx,
    )) as { ok: boolean; result: { diff: string } };
    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("+ BethINI → C:/Tools/BethINI.exe");
  });

  it("plan edit/remove throw title_not_found when absent", async () => {
    vi.mocked(detectMo2Running).mockResolvedValue({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
    const { ctx } = await _fixture();
    const tool = getTool("mo2_configure_executable")!;

    await expect(
      tool.handler({ mode: "plan", action: "edit", title: "Missing", updates: { binary: "C:/x.exe" } }, ctx),
    ).rejects.toThrow(/title_not_found: Missing/);
    await expect(
      tool.handler({ mode: "plan", action: "remove", title: "Missing" }, ctx),
    ).rejects.toThrow(/title_not_found: Missing/);
  });

  it("apply add appends entry and preserves non-custom sections byte-for-byte", async () => {
    vi.mocked(detectMo2Running).mockResolvedValue({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
    const { ctx, iniPath } = await _fixture();
    const before = await readFile(iniPath, "utf8");
    const tool = getTool("mo2_configure_executable")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        action: "add",
        entry: {
          title: "BethINI",
          binary: "C:/Tools/BethINI.exe",
          arguments: "--portable",
          workingDirectory: "C:/Tools",
          ownicon: true,
          hide: false,
          toolbar: true,
        },
      },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    ) as { ok: boolean; result: { executables_count: number } };

    expect(apply.ok).toBe(true);
    expect(apply.result.executables_count).toBe(3);
    const after = await readFile(iniPath, "utf8");
    const parsed = await readMoIni(iniPath);
    expect(parsed.customExecutables.at(-1)).toMatchObject({
      title: "BethINI",
      binary: "C:/Tools/BethINI.exe",
      arguments: "--portable",
      workingDirectory: "C:/Tools",
      ownicon: true,
      hide: false,
      toolbar: true,
    });
    expect(_section(after, "General")).toBe(_section(before, "General"));
    expect(_section(after, "Settings")).toBe(_section(before, "Settings"));
    expect(_section(after, "other")).toBe(_section(before, "other"));
  });

  it("apply remove deletes entry and decrements size", async () => {
    vi.mocked(detectMo2Running).mockResolvedValue({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
    const { ctx, iniPath } = await _fixture();
    const tool = getTool("mo2_configure_executable")!;
    const plan = (await tool.handler(
      { mode: "plan", action: "remove", title: "LOOT" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    );

    const text = await readFile(iniPath, "utf8");
    const parsed = await readMoIni(iniPath);
    expect(parsed.customExecutables.map((entry) => entry.title)).toEqual(["xEdit"]);
    expect(_section(text, "customExecutables")).toContain("size=1");
  });

  it("apply edit merges updates into an existing entry", async () => {
    vi.mocked(detectMo2Running).mockResolvedValue({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
    });
    const { ctx, iniPath } = await _fixture();
    const tool = getTool("mo2_configure_executable")!;
    const plan = (await tool.handler(
      { mode: "plan", action: "edit", title: "xEdit", updates: { arguments: "-FO4 -IKnowWhatImDoing", hide: true } },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    );

    const parsed = await readMoIni(iniPath);
    expect(parsed.customExecutables[0]).toMatchObject({
      title: "xEdit",
      binary: "C:/Tools/xEdit/xEdit.exe",
      arguments: "-FO4 -IKnowWhatImDoing",
      hide: true,
    });
  });
});
