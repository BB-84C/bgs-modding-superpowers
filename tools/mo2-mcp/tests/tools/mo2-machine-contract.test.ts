import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _setup(options: { gamePath?: string; createXEdit?: boolean } = {}): Promise<{ root: string; ctx: ToolContext; gamePath: string }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-mc-"));
  const gamePath = options.gamePath ?? join(root, "Games", "Fallout 4");
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\ngamePath=@ByteArray(" + gamePath.replace(/\\/g, "\\\\") + ")\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  if (options.createXEdit) {
    await mkdir(join(gamePath, "Tools", "OpenCodeXEdit"), { recursive: true });
    await writeFile(join(gamePath, "Tools", "OpenCodeXEdit", "xEdit.exe"), "", "utf8");
  }
  const modsDir = join(root, "mods");
  await mkdir(join(modsDir, "ModA", "Data"), { recursive: true });
  await mkdir(join(modsDir, "ModB"), { recursive: true });

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
  return { root, ctx, gamePath };
}

describe("mo2_machine_contract", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-machine-contract.js");
  });

  it("registers as T1", () => {
    const tool = getTool("mo2_machine_contract");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns profile list paths + archive search roots", async () => {
    const { ctx, root } = await _setup();
    const tool = getTool("mo2_machine_contract")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: {
        profile_list_paths: { modlist_txt: string; profile_dir: string };
        archive_search_roots: Array<{ mod_name: string; is_data_subdir_layout: boolean }>;
      };
    };
    expect(result.ok).toBe(true);
    expect(result.result.profile_list_paths.modlist_txt).toBe(
      join(root, "profiles", "Default", "modlist.txt"),
    );
    expect(result.result.archive_search_roots).toHaveLength(2);
    const modA = result.result.archive_search_roots.find((r) => r.mod_name === "ModA")!;
    const modB = result.result.archive_search_roots.find((r) => r.mod_name === "ModB")!;
    expect(modA.is_data_subdir_layout).toBe(true);
    expect(modB.is_data_subdir_layout).toBe(false);
  });

  it("returns static MO2, game, Stock Game, and xEdit paths", async () => {
    const stockGamePath = join(await mkdtemp(join(tmpdir(), "mo2-stock-game-")), "Stock Game", "Fallout 4");
    const { ctx, root, gamePath } = await _setup({ gamePath: stockGamePath, createXEdit: true });
    const tool = getTool("mo2_machine_contract")!;

    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: {
        mod_organizer_exe: string;
        game_path: string;
        stock_game_path: string | null;
        xedit_target: string | null;
      };
    };

    expect(result.ok).toBe(true);
    expect(result.result.mod_organizer_exe).toBe(join(root, "ModOrganizer.exe"));
    expect(result.result.game_path).toBe(gamePath);
    expect(result.result.stock_game_path).toBe(gamePath);
    expect(result.result.xedit_target).toBe(join(gamePath, "Tools", "OpenCodeXEdit", "xEdit.exe"));
  });

  it("returns null Stock Game and xEdit paths when the layout and executable are absent", async () => {
    const gamePath = join(await mkdtemp(join(tmpdir(), "mo2-game-")), "Steam", "Fallout 4");
    const { ctx } = await _setup({ gamePath });
    const tool = getTool("mo2_machine_contract")!;

    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { stock_game_path: string | null; xedit_target: string | null };
    };

    expect(result.ok).toBe(true);
    expect(result.result.stock_game_path).toBeNull();
    expect(result.result.xedit_target).toBeNull();
  });
});
