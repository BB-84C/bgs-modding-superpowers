/**
 * BUG-10 regression guard: empty-string required fields must produce the
 * stable `invalid_arguments` envelope, not fall through to handler-level
 * `internal_error` like `mod_not_found:`.
 *
 * Symptom (e2e plan run 20260617T002922Z, cases C.5.1-C.5.3):
 *   `mo2_toggle_mod({mode:'plan', name:'', enabled:false})` returned
 *   `{ok:false, code:'internal_error', message:'mod_not_found: '}`. Agents
 *   then can't tell the difference between "you forgot to fill in a required
 *   field" and "the mod genuinely doesn't exist in the modlist".
 *
 * Fix: tighten the Zod schema on required string fields with `.min(1)` so
 * empty strings fail safeParse and dispatch.ts emits the stable
 * `invalid_arguments` envelope before any handler runs.
 *
 * This test loads the REAL registered tool schemas (not inline mocks) so the
 * regression is observed at the same Zod surface used at runtime.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { dispatchToolCall } from "../src/dispatch.js";
import { AuditLogger } from "../src/audit.js";
import { PlanCache } from "../src/plan-apply.js";
import { SnapshotManager } from "../src/snapshot.js";
import { BindingManager, type BindingManagerOptions } from "../src/binding.js";
import { _clearToolsForTests, getTool } from "../src/tool-registry.js";
import type { Config, RawConfig } from "../src/config.js";
import type { ToolContext } from "../src/types.js";

function configFor(root: string, profile = "Default"): Config {
  return {
    mo2Root: root,
    permissionCeiling: "full-control" as RawConfig["permission_ceiling"],
    allowedProfiles: [profile],
    deny: [],
    snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
    auditRoot: join(root, ".mo2-mcp", "audit"),
  };
}

function boundBindingOpts(root: string): BindingManagerOptions {
  return {
    loadConfig: async ({ mo2Root }) => configFor(mo2Root),
    readMoIni: async () => ({
      general: { game: "fallout4", gameName: "Fallout 4", gamePath: root },
      settings: { modDirectory: join(root, "mods") },
    }),
    detectMo2Running: async () => ({
      processRunning: false,
      sharedMemoryPresent: false,
      profileLockHeld: false,
      online: false,
      confidence: "low",
    }),
    createSidecarClient: () => ({
      async start() {},
      async stop() {},
      isReady: () => false,
    }) as never,
    createPipeClient: () => ({
      async discoverAndConnect() {},
      close() {},
      isConnected: () => false,
    }) as never,
    log: () => {},
  };
}

async function makeBoundCtx(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-bug10-"));
  const binding = new BindingManager(boundBindingOpts(root));
  await binding.bind({ mo2Root: root, profile: "Default" });
  return {
    binding,
    sessionId: "bug10-session",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, "snapshots"), "bug10-session"),
    audit: new AuditLogger(join(root, "audit"), "bug10-session"),
  };
}

function responseJson(result: { content: Array<{ type: "text"; text: string }> }): unknown {
  return JSON.parse(result.content[0].text) as unknown;
}

// Compact catalog of tools and the args that should now fail Zod safeParse
// with `invalid_arguments`. Each entry is one concrete reproduction of the
// BUG-10 pattern (empty required string). The full sweep below verifies each
// tool's schema directly to keep the test fast and side-effect-free.
type SchemaCase = {
  tool: string;
  importPath: string;
  rawArgs: Record<string, unknown>;
  /** Field name the test expects in the Zod field_errors output. */
  fieldName: string;
};

const SCHEMA_CASES: SchemaCase[] = [
  // BUG-10 canonical reproducer
  { tool: "mo2_toggle_mod",     importPath: "../src/tools/mo2-toggle-mod.js",     rawArgs: { mode: "plan", name: "", enabled: false }, fieldName: "name" },
  { tool: "mo2_create_mod",     importPath: "../src/tools/mo2-create-mod.js",     rawArgs: { mode: "plan", name: "" }, fieldName: "name" },
  { tool: "mo2_create_separator", importPath: "../src/tools/mo2-create-separator.js", rawArgs: { mode: "plan", name: "" }, fieldName: "name" },
  { tool: "mo2_rename_mod",     importPath: "../src/tools/mo2-rename-mod.js",     rawArgs: { mode: "plan", old_name: "", new_name: "x" }, fieldName: "old_name" },
  { tool: "mo2_rename_profile", importPath: "../src/tools/mo2-rename-profile.js", rawArgs: { mode: "plan", old_name: "", new_name: "x" }, fieldName: "old_name" },
  { tool: "mo2_set_mod_notes",  importPath: "../src/tools/mo2-set-mod-notes.js",  rawArgs: { mode: "plan", name: "", notes: "abc" }, fieldName: "name" },
  { tool: "mo2_edit_meta",      importPath: "../src/tools/mo2-edit-meta.js",      rawArgs: { mode: "plan", name: "", updates: {} }, fieldName: "name" },
  { tool: "mo2_backup_mod",     importPath: "../src/tools/mo2-backup-mod.js",     rawArgs: { mode: "plan", name: "" }, fieldName: "name" },
  { tool: "mo2_set_file_hidden",importPath: "../src/tools/mo2-set-file-hidden.js",rawArgs: { mode: "plan", virtual_path: "", hidden: true }, fieldName: "virtual_path" },
  { tool: "mo2_send_mod_to",    importPath: "../src/tools/mo2-send-mod-to.js",    rawArgs: { mode: "plan", name: "", target_mode: "top" }, fieldName: "name" },
  { tool: "mo2_install",        importPath: "../src/tools/mo2-install.js",        rawArgs: { mode: "plan", archive_path: "", mod_name: "x" }, fieldName: "archive_path" },
  { tool: "mo2_run_tool",       importPath: "../src/tools/mo2-run-tool.js",       rawArgs: { mode: "plan", title: "" }, fieldName: "title" },
  { tool: "mo2_switch_profile", importPath: "../src/tools/mo2-switch-profile.js", rawArgs: { mode: "plan", new_profile: "" }, fieldName: "new_profile" },
  { tool: "mo2_create_profile", importPath: "../src/tools/mo2-create-profile.js", rawArgs: { mode: "plan", name: "" }, fieldName: "name" },
  { tool: "mo2_clone_profile",  importPath: "../src/tools/mo2-clone-profile.js",  rawArgs: { mode: "plan", source: "", target: "Y" }, fieldName: "source" },
  { tool: "mo2_reinstall_mod",  importPath: "../src/tools/mo2-reinstall-mod.js",  rawArgs: { mode: "plan", name: "" }, fieldName: "name" },
  { tool: "mo2_rollback",       importPath: "../src/tools/mo2-rollback.js",       rawArgs: { mode: "plan", snapshot_id: "" }, fieldName: "snapshot_id" },
  { tool: "mo2_restore_profile",importPath: "../src/tools/mo2-restore-profile.js",rawArgs: { mode: "plan", label: "" }, fieldName: "label" },
  { tool: "mo2_search_files",   importPath: "../src/tools/mo2-search-files.js",   rawArgs: { pattern: "" }, fieldName: "pattern" },
  { tool: "mo2_assets_resolve", importPath: "../src/tools/mo2-assets-resolve.js", rawArgs: { virtual_path: "" }, fieldName: "virtual_path" },
  { tool: "mo2_profile_ini_set",importPath: "../src/tools/mo2-profile-ini-set.js",rawArgs: { mode: "plan", ini_name: "game", section: "", key: "k", value: "v" }, fieldName: "section" },
  { tool: "mo2_mod_info",       importPath: "../src/tools/mo2-mod-info.js",       rawArgs: { name: "" }, fieldName: "name" },
];

describe("BUG-10: empty-string required fields fail Zod safeParse, surface invalid_arguments", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    for (const c of SCHEMA_CASES) {
      await import(c.importPath);
    }
  });

  for (const c of SCHEMA_CASES) {
    it(`${c.tool}: empty ${c.fieldName} fails safeParse`, () => {
      const tool = getTool(c.tool);
      expect(tool, `${c.tool} must be registered`).toBeDefined();
      const result = tool!.inputSchema.safeParse(c.rawArgs);
      expect(
        result.success,
        `expected safeParse to fail for empty ${c.fieldName} in ${c.tool}`,
      ).toBe(false);
    });
  }

  // Canonical end-to-end dispatch check: BUG-10 says
  // `mo2_toggle_mod({mode:'plan', name:'', enabled:false})` returned
  // `internal_error mod_not_found:`. After the fix it must return
  // `invalid_arguments` with field_errors naming the empty field.
  it("dispatch: mo2_toggle_mod with empty name returns invalid_arguments (not mod_not_found)", async () => {
    const ctx = await makeBoundCtx();
    const result = await dispatchToolCall({
      toolName: "mo2_toggle_mod",
      rawArgs: { mode: "plan", name: "", enabled: false },
      ctx,
      rules: [],
    });
    const body = responseJson(result) as {
      ok: boolean;
      error: { code: string; message?: string; field_errors?: Record<string, unknown> };
    };
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("invalid_arguments");
    expect(body.error.code).not.toBe("internal_error");
    expect(body.error.message ?? "").not.toMatch(/mod_not_found/);
    expect(body.error.field_errors).toBeDefined();
  });

  // Apply-branch empty plan_id/lease_token must also be rejected as
  // invalid_arguments (was previously plan_expired_or_unknown). The fix is
  // consistent: empty UUIDs are never legitimate, so reject at the schema
  // layer.
  it("dispatch: mo2_toggle_mod apply with empty plan_id returns invalid_arguments", async () => {
    const ctx = await makeBoundCtx();
    const result = await dispatchToolCall({
      toolName: "mo2_toggle_mod",
      rawArgs: { mode: "apply", plan_id: "", lease_token: "x" },
      ctx,
      rules: [],
    });
    const body = responseJson(result) as { ok: boolean; error: { code: string } };
    expect(body.ok).toBe(false);
    expect(body.error.code).toBe("invalid_arguments");
  });

  // Guard against over-zealous tightening: notes/value/arguments fields
  // legitimately accept empty strings. These must continue to pass.
  it("regression guard: mo2_set_mod_notes accepts empty notes (legitimate clear)", () => {
    const tool = getTool("mo2_set_mod_notes")!;
    const result = tool.inputSchema.safeParse({ mode: "plan", name: "RealMod", notes: "" });
    expect(result.success).toBe(true);
  });

  it("regression guard: mo2_profile_ini_set accepts empty value (legitimate clear)", () => {
    const tool = getTool("mo2_profile_ini_set")!;
    const result = tool.inputSchema.safeParse({
      mode: "plan",
      ini_name: "game",
      section: "Display",
      key: "iSize",
      value: "",
    });
    expect(result.success).toBe(true);
  });
});
