/**
 * MO2 MCP server bootstrap.
 *
 * Sequence:
 *   1. Parse env (BGS_MO2_ROOT required)
 *   2. Load .mo2-mcp.json config
 *   3. If permission_ceiling=read-only: probe-test write to MO2_Root → must fail
 *   4. Read ModOrganizer.ini for game/paths
 *   5. Spawn Python sidecar with --game (P-B7)
 *   6. Detect MO2 running (3-tier ladder); connect named pipe if online
 *   7. Wire ToolContext with plans + snapshots + audit (P-F9)
 *   8. Start MCP stdio server, register tools/list + tools/call handlers
 *
 * Tools register via side-effect imports (S3+ adds them); S2 registers ZERO
 * tools — server boots clean and tools/list returns [].
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { randomUUID } from "node:crypto";
import { writeFile, unlink } from "node:fs/promises";
import { join } from "node:path";
import { Lifecycle } from "./lifecycle.js";
import { loadConfig } from "./config.js";
import { readMoIni } from "./mo-ini.js";
import { detectMo2Running } from "./detection.js";
import { PipeClient } from "./pipe-client.js";
import { SidecarClient, type SidecarGame } from "./sidecar-client.js";
import { AuditLogger, hashArgs } from "./audit.js";
import { SnapshotManager } from "./snapshot.js";
import { PlanCache } from "./plan-apply.js";
import { getAllTools, getTool } from "./tool-registry.js";
import { runRules, hasBlocking } from "./pipeline/rules.js";
import { getAllRules } from "./pipeline/registry.js";
import "./pipeline/rules/STOCK001-stock-game-deny.js"; // side-effect: register STOCK001
import "./tools/mo2-status.js"; // side-effect: register mo2_status
import "./tools/mo2-machine-contract.js"; // side-effect: register mo2_machine_contract
import "./tools/mo2-modlist.js"; // side-effect: register mo2_modlist
import "./tools/mo2-pluginlist.js"; // side-effect: register mo2_pluginlist
import "./tools/mo2-mod-info.js"; // side-effect: register mo2_mod_info
import "./tools/mo2-profile-ini-get.js"; // side-effect: register mo2_profile_ini_get
import "./tools/mo2-set-mod-notes.js"; // side-effect: register mo2_set_mod_notes
import "./tools/mo2-edit-meta.js"; // side-effect: register mo2_edit_meta
import "./tools/mo2-profile-ini-set.js"; // side-effect: register mo2_profile_ini_set
import "./tools/mo2-backup-mod.js"; // side-effect: register mo2_backup_mod
import "./tools/mo2-backup-profile.js"; // side-effect: register mo2_backup_profile
import "./tools/mo2-toggle-mod.js"; // side-effect: register mo2_toggle_mod
import "./tools/mo2-toggle-plugin.js"; // side-effect: register mo2_toggle_plugin
import "./tools/mo2-send-mod-to.js"; // side-effect: register mo2_send_mod_to
import "./tools/mo2-rollback.js"; // side-effect: register mo2_rollback
import "./tools/mo2-restore-profile.js"; // side-effect: register mo2_restore_profile
import "./tools/mo2-install.js"; // side-effect: register mo2_install
import "./tools/mo2-run-tool.js"; // side-effect: register mo2_run_tool
import "./tools/mo2-switch-profile.js"; // side-effect: register mo2_switch_profile
import "./tools/mo2-configure-executable.js"; // side-effect: register mo2_configure_executable
import "./tools/mo2-create-mod.js"; // side-effect: register mo2_create_mod
import "./tools/mo2-create-separator.js"; // side-effect: register mo2_create_separator
import "./tools/mo2-rename-mod.js"; // side-effect: register mo2_rename_mod
import "./tools/mo2-reinstall-mod.js"; // side-effect: register mo2_reinstall_mod
import "./tools/mo2-remove-mod.js"; // side-effect: register mo2_remove_mod
import "./tools/mo2-set-file-hidden.js"; // side-effect: register mo2_set_file_hidden
import "./tools/mo2-create-profile.js"; // side-effect: register mo2_create_profile
import type { ToolContext } from "./types.js";

const GAME_MAP: Record<string, SidecarGame> = {
  fallout4: "FALLOUT4",
  skyrimSE: "SKYRIM_SE",
  skyrimLE: "SKYRIM_LE",
  starfield: "STARFIELD",
  oblivion: "OBLIVION",
  falloutNV: "FALLOUT_NV",
};

async function main(): Promise<void> {
  const sessionId = randomUUID();
  const lifecycle = new Lifecycle();
  lifecycle.markStarting();

  const mo2Root = process.env.BGS_MO2_ROOT;
  if (!mo2Root) {
    process.stderr.write("BGS_MO2_ROOT not set\n");
    process.exit(1);
  }

  const config = await loadConfig({ mo2Root });

  // Read-only ceiling probe (charrdge :ro defense-in-depth pattern)
  if (config.permissionCeiling === "read-only") {
    const probePath = join(mo2Root, ".mo2-mcp", "probe");
    try {
      await writeFile(probePath, "probe");
      await unlink(probePath);
      process.stderr.write(
        "read-only ceiling configured but probe-write succeeded; refusing to start\n",
      );
      process.exit(2);
    } catch {
      // Expected: probe-write failed → host actually enforces read-only
    }
  }

  const ini = await readMoIni(join(mo2Root, "ModOrganizer.ini"));
  const profileName = config.allowedProfiles[0];
  const profileDir = join(mo2Root, "profiles", profileName);

  // Spawn sidecar (P-B7 --game propagation)
  const game = GAME_MAP[ini.general.game ?? "fallout4"] ?? "FALLOUT4";
  const sidecar = new SidecarClient();
  try {
    await sidecar.start({
      modsRoot: ini.settings.modDirectory ?? join(mo2Root, "mods"),
      profileDir,
      game,
    });
  } catch (e) {
    process.stderr.write(`[mo2-mcp] sidecar failed to start: ${e}\n`);
    // Continue — asset tools will return sidecar_not_ready
  }

  // MO2 detection ladder
  const detection = await detectMo2Running({ mo2Root, profileDir });
  const pipe = new PipeClient();
  if (detection.online) {
    try {
      await pipe.discoverAndConnect(mo2Root);
    } catch {
      // Offline mode — broker tools return not_connected
    }
  }

  const audit = new AuditLogger(config.auditRoot, sessionId);
  const snapshots = new SnapshotManager(config.snapshotRoot, sessionId);
  const plans = new PlanCache();
  const rules = getAllRules();

  const ctx: ToolContext = {
    config,
    pipeClient: pipe.isConnected() ? pipe : undefined,
    sidecar: sidecar.isReady() ? sidecar : undefined,
    sessionId,
    plans,
    snapshots,
    audit,
  };

  const server = new Server(
    { name: "mo2-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: getAllTools().map((t) => ({
      name: t.name,
      description: t.description,
      inputSchema: t.inputSchema as any, // Zod → JSON Schema
    })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const t0 = Date.now();
    const tool = getTool(req.params.name);
    if (!tool) {
      await audit.log({
        ts: new Date().toISOString(),
        sessionId,
        tool: req.params.name,
        argsHash: hashArgs(req.params.arguments),
        decision: "refused",
        durationMs: Date.now() - t0,
        error: { code: "tool_not_found", message: req.params.name },
      });
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ ok: false, error: { code: "tool_not_found" } }),
          },
        ],
      };
    }

    const args = (req.params.arguments ?? {}) as Record<string, unknown>;
    const findings = await runRules(rules, tool.name, ctx, args);
    if (hasBlocking(findings)) {
      const blocking = findings.find((f) => f.decision === "block")!;
      await audit.log({
        ts: new Date().toISOString(),
        sessionId,
        tool: tool.name,
        argsHash: hashArgs(args),
        decision: "refused",
        ruleFindings: findings,
        durationMs: Date.now() - t0,
        error: { code: blocking.code, message: blocking.message },
      });
      return {
        content: [{ type: "text", text: JSON.stringify({ ok: false, error: blocking }) }],
      };
    }

    try {
      const result = await tool.handler(args, ctx);
      const mode = args.mode as "plan" | "apply" | undefined;
      const resultObj = result as { ok?: boolean; result?: { planId?: string; snapshot_id?: string } } | undefined;
      await audit.log({
        ts: new Date().toISOString(),
        sessionId,
        tool: tool.name,
        mode,
        argsHash: hashArgs(args),
        decision:
          resultObj?.ok === false
            ? "refused"
            : mode === "plan"
            ? "plan_generated"
            : mode === "apply"
            ? "applied"
            : "ok",
        durationMs: Date.now() - t0,
        planId: resultObj?.result?.planId,
        snapshotId: resultObj?.result?.snapshot_id,
      });
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      await audit.log({
        ts: new Date().toISOString(),
        sessionId,
        tool: tool.name,
        argsHash: hashArgs(args),
        decision: "refused",
        durationMs: Date.now() - t0,
        error: { code: "internal_error", message: msg },
      });
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              ok: false,
              error: { code: "internal_error", message: msg },
            }),
          },
        ],
      };
    }
  });

  lifecycle.markReady({
    sidecarPid: undefined,
    brokerPipeName: pipe.isConnected() ? "connected" : undefined,
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write(`mo2-mcp ready (session ${sessionId})\n`);
}

main().catch((e) => {
  process.stderr.write(`mo2-mcp fatal: ${e}\n`);
  process.exit(1);
});
