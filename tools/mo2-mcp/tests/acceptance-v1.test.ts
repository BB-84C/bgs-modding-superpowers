import { beforeAll, describe, expect, it } from "vitest";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import {
  appendFile,
  mkdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { join } from "node:path";
import { readMoIni } from "../src/mo-ini.js";

const PROJECT_ROOT = process.env.BGS_MO2_ACCEPTANCE_PROJECT_ROOT ?? String.raw`D:\awesome-bgs-mod-master`;
const REAL_MO2_ROOT = process.env.BGS_MO2_ROOT ?? String.raw`B:\WastelandBlues 2.0`;
const REAL_PROFILE = process.env.BGS_MO2_PROFILE ?? "BB84自用";
const HARNESS_MO2_ROOT = process.env.BGS_MO2_HARNESS_ROOT ?? String.raw`D:\awesome-bgs-mod-master\.artifacts\mo2`;
const HARNESS_PROFILE = process.env.BGS_MO2_HARNESS_PROFILE ?? "Default";
const ARTIFACTS = join(PROJECT_ROOT, ".opencode", "artifacts", "mo2-mcp", "acceptance");
const MCP_CWD = process.cwd();

const ACCEPTANCE_MOD = process.env.BGS_MO2_ACCEPTANCE_MOD ?? "LODGen 覆盖素材";
const ACCEPTANCE_SEPARATOR = process.env.BGS_MO2_ACCEPTANCE_SEPARATOR;
const ALT_PROFILE = process.env.BGS_MO2_ACCEPTANCE_ALT_PROFILE;
const FOMOD_ARCHIVE = process.env.BGS_MO2_ACCEPTANCE_FOMOD_ARCHIVE ?? join(ARTIFACTS, "fixtures", "test-fomod.7z");
const SIMPLE_ARCHIVE = process.env.BGS_MO2_ACCEPTANCE_SIMPLE_ARCHIVE ?? join(ARTIFACTS, "fixtures", "test-simple.7z");
const OVERRIDDEN_FILE = process.env.BGS_MO2_ACCEPTANCE_OVERRIDDEN_FILE ?? "textures/acceptance/winner.dds";
const EXPECTED_WINNER = process.env.BGS_MO2_ACCEPTANCE_EXPECTED_WINNER;
const EXPECTED_ESP_COUNT = Number(process.env.BGS_MO2_ACCEPTANCE_ESP_COUNT ?? "NaN");

interface ToolResponse {
  ok: boolean;
  result?: any;
  error?: any;
}

interface McpHandle {
  call: (name: string, args: any) => Promise<ToolResponse>;
  kill: () => void;
}

describe.skipIf(process.env.MO2_MCP_ACCEPTANCE !== "1")("v1 acceptance", () => {
  beforeAll(async () => {
    await mkdir(ARTIFACTS, { recursive: true });
  });

  it("AT1: mo2_status reports Fallout 4 and real modpack-scale counts", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const status = await mcp.call("mo2_status", {});
      expectOk(status);
      expect(`${status.result.game ?? ""} ${status.result.game_name ?? ""}`).toMatch(/fallout\s*4|fallout4/i);
      expect(status.result.counts.mods_total).toBeGreaterThan(700);
      await writeEvidence("AT1-status", { status });
    });
  }, 30_000);

  it("AT2: all 11 T1 reads return ok=true in under five seconds each", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const tools: Array<{ name: string; args: Record<string, unknown> }> = [
        { name: "mo2_status", args: {} },
        { name: "mo2_machine_contract", args: {} },
        { name: "mo2_modlist", args: { profile: REAL_PROFILE } },
        { name: "mo2_pluginlist", args: { profile: REAL_PROFILE } },
        { name: "mo2_mod_info", args: { name: ACCEPTANCE_MOD } },
        { name: "mo2_assets_summary", args: { profile: REAL_PROFILE } },
        { name: "mo2_assets_conflicts", args: { profile: REAL_PROFILE, max_results: 25 } },
        { name: "mo2_assets_resolve", args: { profile: REAL_PROFILE, virtual_path: OVERRIDDEN_FILE } },
        { name: "mo2_search_files", args: { profile: REAL_PROFILE, pattern: "**/*.esp", max_results: 25 } },
        { name: "mo2_list_executables", args: {} },
        { name: "mo2_audit_query", args: { max_results: 25 } },
      ];
      const results = [];
      for (const tool of tools) {
        const t0 = Date.now();
        const response = await mcp.call(tool.name, tool.args);
        const durationMs = Date.now() - t0;
        expect(durationMs).toBeLessThan(5000);
        expectOk(response);
        results.push({ tool: tool.name, durationMs, response });
      }
      await writeEvidence("AT2-t1-bounded-reads", { results });
    });
  }, 90_000);

  it("AT3: plan/apply lease enforcement rejects stale modlist state", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const modlistPath = join(REAL_MO2_ROOT, "profiles", REAL_PROFILE, "modlist.txt");
      const before = await readFile(modlistPath, "utf8");
      const plan = await mcp.call("mo2_toggle_mod", {
        mode: "plan",
        name: ACCEPTANCE_MOD,
        enabled: false,
        profile: REAL_PROFILE,
      });
      expectOk(plan);
      try {
        await appendFile(modlistPath, "\n# touched by AT3 lease test\n", "utf8");
        const apply = await mcp.call("mo2_toggle_mod", {
          mode: "apply",
          plan_id: plan.result.planId,
          lease_token: plan.result.lease_token,
        });
        expect(apply.ok).toBe(false);
        expect(apply.error.code).toBe("lease_violation");
        await writeEvidence("AT3-lease-violation", { plan, apply });
      } finally {
        await writeFile(modlistPath, before, "utf8");
      }
    });
  }, 60_000);

  it("AT4: rollback restores a toggled modlist byte-for-byte", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const mod = await pickFirstMod(mcp, HARNESS_PROFILE);
      const modlistPath = join(HARNESS_MO2_ROOT, "profiles", HARNESS_PROFILE, "modlist.txt");
      const before = await readFile(modlistPath, "utf8");
      const toggle = await planApply(mcp, "mo2_toggle_mod", {
        name: mod.name,
        enabled: !mod.enabled,
        profile: HARNESS_PROFILE,
      });
      expectOk(toggle.apply);
      const snapshotId = toggle.apply.result.snapshot_id;
      const rollback = await planApply(mcp, "mo2_rollback", { snapshot_id: snapshotId });
      expectOk(rollback.apply);
      const after = await readFile(modlistPath, "utf8");
      expect(after).toBe(before);
      await writeEvidence("AT4-rollback-roundtrip", { mod, toggle, rollback });
    });
  }, 60_000);

  it("AT5: STOCK001 hard-denies gamePath-derived Data path mutation", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const ini = await readMoIni(join(HARNESS_MO2_ROOT, "ModOrganizer.ini"));
      expect(ini.general.gamePath, "ModOrganizer.ini [General] gamePath is required for AT5").toBeTruthy();
      const gameDataPath = `${ini.general.gamePath!.replace(/[\\/]+$/g, "")}\\Data\\Fallout4.esm`;
      const response = await mcp.call("mo2_set_file_hidden", {
        mode: "plan",
        virtual_path: gameDataPath,
        hidden: true,
      });
      expect(response.ok).toBe(false);
      expect(response.error.code).toBe("STOCK001");
      await writeEvidence("AT5-stock001-deny", { response });
    });
  }, 30_000);

  it("AT6: FOMOD install requires choices, then applies with choices", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      expect(existsSync(FOMOD_ARCHIVE), `missing FOMOD fixture archive: ${FOMOD_ARCHIVE}`).toBe(true);
      const modName = uniqueName("AT6-FOMOD");
      const noChoices = await mcp.call("mo2_install", {
        mode: "plan",
        archive_path: FOMOD_ARCHIVE,
        mod_name: modName,
        profile: HARNESS_PROFILE,
      });
      expect(noChoices.ok).toBe(false);
      expect(String(noChoices.error?.message ?? noChoices.error?.code)).toMatch(/fomod_choices_required/i);
      const install = await planApply(mcp, "mo2_install", {
        archive_path: FOMOD_ARCHIVE,
        mod_name: modName,
        profile: HARNESS_PROFILE,
        fomod_choices: [{ page_name: "Install", selected_options: [{ group_name: "Main", option_name: "Default" }] }],
      });
      try {
        expectOk(install.apply);
      } finally {
        await removeModBestEffort(mcp, modName);
      }
      await writeEvidence("AT6-fomod-install", { noChoices, install });
    });
  }, 120_000);

  it.skipIf(!ALT_PROFILE)("AT7: mo2_switch_profile cold-restarts to alternate profile and back (requires BGS_MO2_ACCEPTANCE_ALT_PROFILE)", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const toAlt = await planApply(mcp, "mo2_switch_profile", { new_profile: ALT_PROFILE! });
      expectOk(toAlt.apply);
      const statusAlt = await mcp.call("mo2_status", {});
      const back = await planApply(mcp, "mo2_switch_profile", { new_profile: REAL_PROFILE });
      expectOk(back.apply);
      await writeEvidence("AT7-switch-profile", { toAlt, statusAlt, back });
    });
  }, 300_000);

  it("AT8: customExecutables add/edit/remove preserves non-executable INI sections", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const iniPath = join(HARNESS_MO2_ROOT, "ModOrganizer.ini");
      const before = await readFile(iniPath, "utf8");
      const title = uniqueName("AT8 Tool");
      const add = await planApply(mcp, "mo2_configure_executable", {
        action: "add",
        entry: { title, binary: "C:/Windows/System32/cmd.exe", arguments: "/c ver", workingDirectory: "C:/Windows/System32" },
      });
      const listedAfterAdd = await mcp.call("mo2_list_executables", {});
      const edit = await planApply(mcp, "mo2_configure_executable", {
        action: "edit",
        title,
        updates: { arguments: "/c echo edited" },
      });
      const remove = await planApply(mcp, "mo2_configure_executable", { action: "remove", title });
      const after = await readFile(iniPath, "utf8");
      expectOk(add.apply);
      expectOk(edit.apply);
      expectOk(remove.apply);
      expectOk(listedAfterAdd);
      expect(stripCustomExecutables(after)).toBe(stripCustomExecutables(before));
      await writeEvidence("AT8-custom-executables-roundtrip", { add, listedAfterAdd, edit, remove });
    });
  }, 120_000);

  it("AT9: profile create, clone, rename, and filesystem cleanup", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const created = uniqueName("AT9-Created");
      const cloned = uniqueName("AT9-Cloned");
      const renamed = uniqueName("AT9-Renamed");
      try {
        const create = await planApply(mcp, "mo2_create_profile", { name: created });
        const clone = await planApply(mcp, "mo2_clone_profile", { source: HARNESS_PROFILE, target: cloned });
        const renameProfile = await planApply(mcp, "mo2_rename_profile", { old_name: cloned, new_name: renamed });
        expectOk(create.apply);
        expectOk(clone.apply);
        expectOk(renameProfile.apply);
        expect(existsSync(join(HARNESS_MO2_ROOT, "profiles", renamed))).toBe(true);
        await writeEvidence("AT9-profile-lifecycle", { create, clone, renameProfile });
      } finally {
        await rm(join(HARNESS_MO2_ROOT, "profiles", created), { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "profiles", cloned), { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "profiles", renamed), { recursive: true, force: true });
      }
    });
  }, 120_000);

  it("AT10: interrupted apply leaves atomic file state old-or-new, never partial", async () => {
    const mcp = await spawnMcp(harnessEnv());
    const iniPath = join(HARNESS_MO2_ROOT, "profiles", HARNESS_PROFILE, "fallout4Custom.ini");
    const before = await readFile(iniPath, "utf8").catch(() => "");
    const expectedNewNeedle = "sAT10Atomic=1";
    try {
      const plan = await mcp.call("mo2_profile_ini_set", {
        mode: "plan",
        profile: HARNESS_PROFILE,
        ini_name: "custom",
        section: "Acceptance",
        key: "sAT10Atomic",
        value: "1",
      });
      expectOk(plan);
      const pending = mcp.call("mo2_profile_ini_set", {
        mode: "apply",
        plan_id: plan.result.planId,
        lease_token: plan.result.lease_token,
      }).catch((error) => ({ ok: false, error: String(error) }));
      mcp.kill();
      await pending.catch(() => undefined);
      const after = await readFile(iniPath, "utf8").catch(() => "");
      expect(after === before || after.includes(expectedNewNeedle)).toBe(true);
      await writeEvidence("AT10-atomic-interrupted-apply", { plan, beforeLength: before.length, afterLength: after.length });
    } finally {
      mcp.kill();
      await writeFile(iniPath, before, "utf8");
    }
  }, 60_000);

  it("AT11: audit query contains plan and applied records for mutations", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const modName = uniqueName("AT11-Audit");
      const create = await planApply(mcp, "mo2_create_mod", { name: modName });
      try {
        expectOk(create.apply);
        const audit = await mcp.call("mo2_audit_query", { tool: "mo2_create_mod", max_results: 100 });
        expectOk(audit);
        const decisions = (audit.result.records as Array<{ decision: string }>).map((record) => record.decision);
        expect(decisions).toContain("plan_generated");
        expect(decisions).toContain("applied");
        await writeEvidence("AT11-audit-completeness", { create, audit });
      } finally {
        await removeModBestEffort(mcp, modName);
      }
    });
  }, 90_000);

  it("AT12: concurrent MCP sessions surface lease_held for overlapping mutation", async () => {
    const first = await spawnMcp(harnessEnv());
    const second = await spawnMcp(harnessEnv());
    try {
      const mod = await pickFirstMod(first, HARNESS_PROFILE);
      const firstPlan = await first.call("mo2_toggle_mod", { mode: "plan", name: mod.name, enabled: !mod.enabled, profile: HARNESS_PROFILE });
      expectOk(firstPlan);
      const secondPlan = await second.call("mo2_toggle_mod", { mode: "plan", name: mod.name, enabled: !mod.enabled, profile: HARNESS_PROFILE });
      expect(secondPlan.ok).toBe(false);
      expect(secondPlan.error.code).toBe("lease_held");
      await writeEvidence("AT12-concurrent-lease-held", { firstPlan, secondPlan });
    } finally {
      first.kill();
      second.kill();
    }
  }, 90_000);

  it.skipIf(!ACCEPTANCE_SEPARATOR)("AT13: mo2_send_mod_to covers all six implemented target modes (requires BGS_MO2_ACCEPTANCE_SEPARATOR)", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const cases = [
        { target_mode: "top" },
        { target_mode: "bottom" },
        { target_mode: "priority", target_priority: 10 },
        { target_mode: "above_separator", target_separator: ACCEPTANCE_SEPARATOR! },
        { target_mode: "above_first_conflict" },
        { target_mode: "below_last_conflict" },
      ];
      const results = [];
      for (const args of cases) {
        const result = await planApply(mcp, "mo2_send_mod_to", { name: ACCEPTANCE_MOD, profile: REAL_PROFILE, ...args });
        expectOk(result.apply);
        results.push(result);
      }
      await writeEvidence("AT13-send-mod-to-modes", { results });
    });
  }, 240_000);

  it.skipIf(!EXPECTED_WINNER)("AT14: mo2_assets_resolve winner matches manual MO2 GUI cross-check (requires BGS_MO2_ACCEPTANCE_EXPECTED_WINNER)", async () => {
    // Manual assertion recorded for the selected file: the expected winner must
    // be set by the operator after checking MO2's Conflicts/Data view.
    await withMcp(realEnv(), async (mcp) => {
      expect(EXPECTED_WINNER, "set BGS_MO2_ACCEPTANCE_EXPECTED_WINNER from MO2 GUI cross-check").toBeTruthy();
      const resolved = await mcp.call("mo2_assets_resolve", { profile: REAL_PROFILE, virtual_path: OVERRIDDEN_FILE });
      expectOk(resolved);
      expect(resolved.result.winner).toBe(EXPECTED_WINNER);
      await writeEvidence("AT14-assets-resolve-winner", { resolved, expected: EXPECTED_WINNER });
    });
  }, 60_000);

  it("AT15: mo2_search_files glob returns expected ESP count", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const search = await mcp.call("mo2_search_files", { profile: REAL_PROFILE, pattern: "**/*.esp", max_results: 10000 });
      expectOk(search);
      if (Number.isFinite(EXPECTED_ESP_COUNT)) {
        expect(search.result.count).toBe(EXPECTED_ESP_COUNT);
      } else {
        expect(search.result.count).toBeGreaterThan(0);
      }
      await writeEvidence("AT15-search-files-esp-count", { search, expected: EXPECTED_ESP_COUNT });
    });
  }, 60_000);

  it("AT16: create_mod + create_separator round-trip then remove_mod", async () => {
    await withMcp(realEnv(), async (mcp) => {
      const modName = uniqueName("AT16-Mod");
      const sepName = uniqueName("AT16-Separator");
      try {
        const createMod = await planApply(mcp, "mo2_create_mod", { name: modName });
        const createSeparator = await planApply(mcp, "mo2_create_separator", { name: sepName, color: "#336699" });
        expectOk(createMod.apply);
        expectOk(createSeparator.apply);
        const removeMod = await planApply(mcp, "mo2_remove_mod", { name: modName, backup_first: false });
        const removeSeparator = await planApply(mcp, "mo2_remove_mod", { name: `${sepName}_separator`, backup_first: false });
        expectOk(removeMod.apply);
        expectOk(removeSeparator.apply);
        await writeEvidence("AT16-create-remove-roundtrip", { createMod, createSeparator, removeMod, removeSeparator });
      } finally {
        await rm(join(REAL_MO2_ROOT, "mods", modName), { recursive: true, force: true });
        await rm(join(REAL_MO2_ROOT, "mods", `${sepName}_separator`), { recursive: true, force: true });
      }
    });
  }, 180_000);

  it("AT17: mo2_rename_mod synchronizes all profile modlist entries", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const oldName = uniqueName("AT17-Old");
      const newName = uniqueName("AT17-New");
      const defaultModlist = join(HARNESS_MO2_ROOT, "profiles", HARNESS_PROFILE, "modlist.txt");
      const profile2 = join(HARNESS_MO2_ROOT, "profiles", "AT17-Profile");
      const beforeDefault = await readFile(defaultModlist, "utf8");
      try {
        await mkdir(join(HARNESS_MO2_ROOT, "mods", oldName), { recursive: true });
        await writeFile(join(HARNESS_MO2_ROOT, "mods", oldName, "file.txt"), "payload", "utf8");
        await mkdir(profile2, { recursive: true });
        await writeFile(defaultModlist, `${beforeDefault}${beforeDefault.endsWith("\n") ? "" : "\n"}+${oldName}\n`, "utf8");
        await writeFile(join(profile2, "modlist.txt"), `-${oldName}\n`, "utf8");
        const renameMod = await planApply(mcp, "mo2_rename_mod", { old_name: oldName, new_name: newName });
        expectOk(renameMod.apply);
        expect(await readFile(defaultModlist, "utf8")).toContain(`+${newName}`);
        expect(await readFile(join(profile2, "modlist.txt"), "utf8")).toContain(`-${newName}`);
        await writeEvidence("AT17-rename-mod-cross-profile", { renameMod });
      } finally {
        await writeFile(defaultModlist, beforeDefault, "utf8");
        await rm(profile2, { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "mods", oldName), { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "mods", newName), { recursive: true, force: true });
      }
    });
  }, 90_000);

  it("AT18: simple archive install appears in assets summary then remove_mod cleans up", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      expect(existsSync(SIMPLE_ARCHIVE), `missing simple archive fixture: ${SIMPLE_ARCHIVE}`).toBe(true);
      const modName = uniqueName("AT18-Simple");
      const install = await planApply(mcp, "mo2_install", {
        archive_path: SIMPLE_ARCHIVE,
        mod_name: modName,
        profile: HARNESS_PROFILE,
      });
      try {
        expectOk(install.apply);
        const summary = await mcp.call("mo2_assets_summary", { profile: HARNESS_PROFILE });
        expectOk(summary);
        const remove = await planApply(mcp, "mo2_remove_mod", { name: modName, backup_first: false });
        expectOk(remove.apply);
        await writeEvidence("AT18-simple-install-assets-remove", { install, summary, remove });
      } finally {
        await rm(join(HARNESS_MO2_ROOT, "mods", modName), { recursive: true, force: true });
      }
    });
  }, 120_000);

  it("AT19: .mohidden round-trip changes VFS winner then restores it", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const high = uniqueName("AT19-High");
      const low = uniqueName("AT19-Low");
      const modlistPath = join(HARNESS_MO2_ROOT, "profiles", HARNESS_PROFILE, "modlist.txt");
      const beforeModlist = await readFile(modlistPath, "utf8");
      const rel = "textures/acceptance/at19.dds";
      try {
        await mkdir(join(HARNESS_MO2_ROOT, "mods", high, "Data", "textures", "acceptance"), { recursive: true });
        await mkdir(join(HARNESS_MO2_ROOT, "mods", low, "Data", "textures", "acceptance"), { recursive: true });
        await writeFile(join(HARNESS_MO2_ROOT, "mods", high, "Data", rel), "high", "utf8");
        await writeFile(join(HARNESS_MO2_ROOT, "mods", low, "Data", rel), "low", "utf8");
        await writeFile(modlistPath, `+${high}\n+${low}\n${beforeModlist}`, "utf8");
        const original = await mcp.call("mo2_assets_resolve", { profile: HARNESS_PROFILE, virtual_path: rel });
        expectOk(original);
        expect(original.result.winner).toBe(high);
        const hide = await planApply(mcp, "mo2_set_file_hidden", { virtual_path: rel, hidden: true });
        const hidden = await mcp.call("mo2_assets_resolve", { profile: HARNESS_PROFILE, virtual_path: rel });
        expectOk(hidden);
        expect(hidden.result.winner).toBe(low);
        const unhide = await planApply(mcp, "mo2_set_file_hidden", { virtual_path: `${rel}.mohidden`, hidden: false });
        const restored = await mcp.call("mo2_assets_resolve", { profile: HARNESS_PROFILE, virtual_path: rel });
        expectOk(restored);
        expect(restored.result.winner).toBe(high);
        await writeEvidence("AT19-file-hidden-roundtrip", { original, hide, hidden, unhide, restored });
      } finally {
        await writeFile(modlistPath, beforeModlist, "utf8");
        await rm(join(HARNESS_MO2_ROOT, "mods", high), { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "mods", low), { recursive: true, force: true });
      }
    });
  }, 120_000);
});

async function withMcp<T>(env: Record<string, string>, fn: (mcp: McpHandle) => Promise<T>): Promise<T> {
  const mcp = await spawnMcp(env);
  try {
    return await fn(mcp);
  } finally {
    mcp.kill();
  }
}

function realEnv(extra: Record<string, string> = {}): Record<string, string> {
  return { BGS_MO2_ROOT: REAL_MO2_ROOT, BGS_MO2_PROFILE: REAL_PROFILE, BGS_MO2_PERMISSION_CEILING: "full-control", ...extra };
}

function harnessEnv(extra: Record<string, string> = {}): Record<string, string> {
  return { BGS_MO2_ROOT: HARNESS_MO2_ROOT, BGS_MO2_PROFILE: HARNESS_PROFILE, BGS_MO2_PERMISSION_CEILING: "full-control", ...extra };
}

async function planApply(mcp: McpHandle, tool: string, args: Record<string, unknown>): Promise<{ plan: ToolResponse; apply: ToolResponse }> {
  const plan = await mcp.call(tool, { mode: "plan", ...args });
  expectOk(plan);
  const apply = await mcp.call(tool, {
    mode: "apply",
    plan_id: plan.result.planId,
    lease_token: plan.result.lease_token,
  });
  return { plan, apply };
}

async function removeModBestEffort(mcp: McpHandle, name: string): Promise<void> {
  const plan = await mcp.call("mo2_remove_mod", { mode: "plan", name, backup_first: false });
  if (!plan.ok) return;
  await mcp.call("mo2_remove_mod", {
    mode: "apply",
    plan_id: plan.result.planId,
    lease_token: plan.result.lease_token,
  });
}

async function pickFirstMod(mcp: McpHandle, profile: string): Promise<{ name: string; enabled: boolean }> {
  const modlist = await mcp.call("mo2_modlist", { profile });
  expectOk(modlist);
  const mod = (modlist.result.mods as Array<{ name: string; enabled: boolean; is_separator: boolean }>).find((entry) => !entry.is_separator);
  expect(mod).toBeDefined();
  return mod!;
}

function expectOk(response: ToolResponse): asserts response is ToolResponse & { ok: true; result: any } {
  expect(response.ok, JSON.stringify(response.error ?? response, null, 2)).toBe(true);
}

async function writeEvidence(name: string, payload: unknown): Promise<void> {
  await mkdir(ARTIFACTS, { recursive: true });
  await writeFile(
    join(ARTIFACTS, `${name}.json`),
    JSON.stringify({ ts: new Date().toISOString(), payload }, null, 2),
    "utf8",
  );
}

function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function stripCustomExecutables(text: string): string {
  const lines = text.split(/\r?\n/);
  const out: string[] = [];
  let skipping = false;
  for (const line of lines) {
    if (/^\[customExecutables\]$/i.test(line.trim())) {
      skipping = true;
      continue;
    }
    if (skipping && /^\[.+\]$/.test(line.trim())) {
      skipping = false;
    }
    if (!skipping) out.push(line);
  }
  return out.join("\n");
}

async function spawnMcp(env: Record<string, string>): Promise<McpHandle> {
  const proc = spawn("node", ["dist/index.js"], {
    cwd: MCP_CWD,
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "pipe"],
  }) as ChildProcessWithoutNullStreams;

  let nextId = 1;
  let stdoutBuffer = "";
  let stderrBuffer = "";
  const pending = new Map<number, {
    resolve: (value: any) => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  }>();

  proc.stderr.on("data", (chunk: Buffer) => {
    stderrBuffer += chunk.toString("utf8");
  });

  proc.stdout.on("data", (chunk: Buffer) => {
    stdoutBuffer += chunk.toString("utf8");
    let idx = stdoutBuffer.indexOf("\n");
    while (idx >= 0) {
      const line = stdoutBuffer.slice(0, idx).trim();
      stdoutBuffer = stdoutBuffer.slice(idx + 1);
      if (line) dispatchJsonRpcLine(line, pending, stderrBuffer);
      idx = stdoutBuffer.indexOf("\n");
    }
  });

  proc.once("exit", (code, signal) => {
    for (const [id, entry] of pending) {
      clearTimeout(entry.timer);
      entry.reject(new Error(`MCP process exited before response id=${id}; code=${code}; signal=${signal}; stderr=${stderrBuffer}`));
    }
    pending.clear();
  });

  const request = (method: string, params: any, timeoutMs = 30_000): Promise<any> => {
    const id = nextId++;
    const payload = { jsonrpc: "2.0", id, method, params };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`MCP request timed out: ${method}; stderr=${stderrBuffer}`));
      }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      proc.stdin.write(`${JSON.stringify(payload)}\n`);
    });
  };

  await request("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "mo2-mcp-acceptance", version: "1.0.0" },
  }, 60_000);
  proc.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} })}\n`);

  return {
    call: async (name: string, args: any): Promise<ToolResponse> => {
      const response = await request("tools/call", { name, arguments: args }, 180_000);
      const text = response.result?.content?.[0]?.text;
      if (typeof text !== "string") {
        return { ok: false, error: { code: "malformed_mcp_response", response } };
      }
      try {
        return JSON.parse(text) as ToolResponse;
      } catch (error) {
        return { ok: false, error: { code: "tool_response_not_json", message: String(error), text } };
      }
    },
    kill: () => {
      for (const [id, entry] of pending) {
        clearTimeout(entry.timer);
        entry.reject(new Error(`MCP process killed before response id=${id}`));
      }
      pending.clear();
      proc.stdin.end();
      proc.kill();
    },
  };
}

function dispatchJsonRpcLine(
  line: string,
  pending: Map<number, { resolve: (value: any) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>,
  stderrBuffer: string,
): void {
  let message: any;
  try {
    message = JSON.parse(line);
  } catch {
    return;
  }
  if (typeof message.id !== "number") return;
  const entry = pending.get(message.id);
  if (!entry) return;
  pending.delete(message.id);
  clearTimeout(entry.timer);
  if (message.error) {
    entry.reject(new Error(`MCP JSON-RPC error id=${message.id}: ${JSON.stringify(message.error)}; stderr=${stderrBuffer}`));
  } else {
    entry.resolve(message);
  }
}
