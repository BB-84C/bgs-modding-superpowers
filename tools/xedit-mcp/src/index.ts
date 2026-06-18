import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { statSync } from "node:fs";

import type { DaemonAdapter } from "./daemon-adapter.js";
import type { Envelope } from "./types.js";
import { createAuditLogger } from "./audit.js";
import { defaultRegistry } from "./rules/registry.js";
import { xeditSessionTool } from "./tools/session.js";
import { xeditListCapabilitiesTool } from "./tools/list-capabilities.js";
import { makeFindRecordHandler } from "./tools/find-record.js";
import { makeReadRecordHandler } from "./tools/read-record.js";
import { makeInspectConflictsHandler } from "./tools/inspect-conflicts.js";
import { makeInspectConflictsDeepHandler } from "./tools/inspect-conflicts-deep.js";
import { makeFindRecordsByPatternHandler } from "./tools/find-records-by-pattern.js";
import { makeCreateChildRecordHandler } from "./tools/create-child-record.js";
import { makeNavigateAncestryHandler } from "./tools/navigate-ancestry.js";
import { makeCallHandler } from "./tools/call.js";
import { refuse } from "./envelope.js";
import { MCP_ERROR_CODES } from "./types.js";
import { launchDaemon, type LaunchOptions, type LaunchedDaemon } from "./launch.js";

export interface ServerToolsetOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  auditDir?: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export interface ServerToolset {
  list: () => string[];
  invoke: (name: string, args: Record<string, unknown>) => Promise<Envelope>;
}

export function buildServerToolset(opts: ServerToolsetOptions): ServerToolset {
  const audit = createAuditLogger({
    baseDir: opts.auditDir ?? join(tmpdir(), "xedit-mcp-audit"),
  });
  const registry = defaultRegistry();
  const session = xeditSessionTool({
    adapter: opts.adapter,
    sessionId: opts.sessionId,
    daemonPid: opts.daemonPid ?? process.pid,
    mcpModeActive: opts.mcpModeActive,
    audit,
  });
  const getCtx = session.getContext;

  const listCaps = xeditListCapabilitiesTool({ adapter: opts.adapter, getContext: getCtx, audit });
  const find = makeFindRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const read = makeReadRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const inspect = makeInspectConflictsHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const inspectDeep = makeInspectConflictsDeepHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const findByPattern = makeFindRecordsByPatternHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const createChild = makeCreateChildRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const navigateAncestry = makeNavigateAncestryHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const call = makeCallHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });

  const handlers: Record<string, (a: Record<string, unknown>) => Promise<Envelope>> = {
    xedit_session: session.tool,
    xedit_list_capabilities: listCaps,
    xedit_find_record: find,
    xedit_read_record: read,
    xedit_inspect_conflicts: inspect,
    xedit_inspect_conflicts_deep: inspectDeep,
    xedit_find_records_by_pattern: findByPattern,
    xedit_create_child_record: createChild,
    xedit_navigate_ancestry: navigateAncestry,
    xedit_call: call,
  };

  return {
    list: () => Object.keys(handlers),
    invoke: async (name, args) => {
      const h = handlers[name];
      if (!h) {
        return refuse({
          tool: name,
          summary: `Unknown tool: ${name}`,
          code: MCP_ERROR_CODES.INVALID_REQUEST,
          hint: "List available tools via the MCP listTools request.",
        });
      }
      return h(args);
    },
  };
}

// =============================================================================
// Production stdio MCP server: NON-BLOCKING state machine.
// =============================================================================
//
// Why non-blocking: launching xEdit through MO2's control plane takes 60-180s
// because xEdit has to parse the active load order before its automation-serve
// pipe answers. If tool calls block on that, every MCP client hits its turn
// timeout and the agent sees a wall of errors. Instead, the server tracks
// the daemon's lifecycle in memory and ALL tool calls return immediately.
//
// Tool surface (9 total):
//
//   LIFECYCLE / HEALTH (3)
//     xedit_status   pure read — returns { status: "not_started" | "starting" | "ready" | "failed", ... }
//                    Never blocks. Never modifies state. Use this to poll.
//     xedit_start    if not_started/failed: kick off background launch.
//                    Returns immediately with current status.
//     xedit_health   when ready: send system.ping through the named pipe to
//                    confirm the daemon is still responsive (vs zombie).
//                    Otherwise: returns the same shape as xedit_status.
//
//   DOMAIN TOOLS (6)
//     xedit_session            non-blocking. If status=ready: returns the rich
//                              session envelope. If status=not_started: auto-
//                              kicks-off launch. Otherwise: returns current
//                              status + hint to poll xedit_status.
//     xedit_list_capabilities  status=ready required, otherwise fast-fail with
//     xedit_find_record        code "not_ready". The fast-fail envelope carries
//     xedit_read_record        the current status so the agent knows whether to
//     xedit_inspect_conflicts  poll or kick off a launch.
//     xedit_call
//
// Launch configuration:
//   Env vars (preferred for harness MCP server config):
//     BGS_MO2_ROOT             absolute path to the user's MO2 install root
//                              (the directory containing ModOrganizer.exe).
//                              Drives the launcher default + plugins.txt
//                              lookup. REQUIRED for end-user installs.
//     BGS_XEDIT_CLIENT_SCRIPT  absolute path to tools/mo2-vfs-launcher/xedit-client.ps1
//     BGS_XEDIT_LAUNCHER_PATH  absolute path to xEdit.exe. If unset and
//                              BGS_MO2_ROOT is set, defaults to
//                              <BGS_MO2_ROOT>/tools/xEdit/xEdit.exe.
//     BGS_XEDIT_GAME_MODE      xEdit game mode string, e.g. "Fallout4"
//     BGS_MO2_PROFILE          optional, defaults to "Default"
//   Per-call overrides (xedit_start args, win over env vars):
//     moRoot, launcherPath, gameMode, dataPath, pluginsFile, moProfile
//   Auto-detect fallback (dev workflow only):
//     <plugin-root>/tools/mo2-vfs-launcher/xedit-client.ps1
//     <plugin-root>/.artifacts/mo2/tools/xEdit/xEdit.exe — used ONLY when
//     the dev sandbox actually exists. End-user clones don't carry this
//     tree, so the fallback fails cleanly with a "set BGS_MO2_ROOT" error.
//
// Pre-req for any successful launch: MO2 must already be running with the
// Mo2AgentControl Python plugin loaded. The setting-up-bgs-modding-environment
// skill installs the Python plugin and launches MO2 visibly via
// scripts/start-mo2.ps1.

interface ResolvedLaunchOpts extends LaunchOptions {}

interface LaunchOverrides {
  moRoot?: string;
  launcherPath?: string;
  gameMode?: string;
  dataPath?: string;
  pluginsFile?: string;
  moProfile?: string;
  iKnowWhatImDoing?: boolean;
}

function resolveLaunchOpts(overrides: LaunchOverrides = {}): ResolvedLaunchOpts | { error: string } {
  const envClient = process.env.BGS_XEDIT_CLIENT_SCRIPT;
  const envLauncher = process.env.BGS_XEDIT_LAUNCHER_PATH;
  const envGameMode = process.env.BGS_XEDIT_GAME_MODE;
  const envProfile = process.env.BGS_MO2_PROFILE ?? "Default";
  const envDataPath = process.env.BGS_XEDIT_DATA_PATH;
  const envPluginsFile = process.env.BGS_XEDIT_PLUGINS_FILE;
  const envMoRoot = process.env.BGS_MO2_ROOT;

  // Resolution priority: explicit overrides (from xedit_start args) > env vars > auto-detect.
  const moRoot = overrides.moRoot ?? envMoRoot;
  const gameMode = overrides.gameMode ?? envGameMode;
  const moProfile = overrides.moProfile ?? envProfile;
  const dataPath = overrides.dataPath ?? envDataPath;
  const pluginsFile = overrides.pluginsFile ?? envPluginsFile;
  // Consent is per-launch and explicit only. No env-var fallback by design:
  // the dev workflow must opt into mutations via the MCP tool arg so the
  // audit log captures the consent decision at the call site.
  const iKnowWhatImDoing = overrides.iKnowWhatImDoing === true ? true : undefined;
  // launcherPath default: explicit override > env > <moRoot>/tools/xEdit/xEdit.exe
  const launcherPath = overrides.launcherPath
    ?? envLauncher
    ?? (moRoot ? resolve(moRoot, "tools/xEdit/xEdit.exe") : undefined);

  if (envClient && launcherPath && gameMode) {
    return {
      clientScript: envClient,
      launcherPath,
      gameMode,
      moProfile,
      moRoot,
      dataPath,
      pluginsFile,
      iKnowWhatImDoing,
    };
  }

  try {
    const thisFile = fileURLToPath(import.meta.url);
    const pluginRoot = resolve(dirname(thisFile), "..", "..", "..");
    const candidateClient = envClient ?? resolve(pluginRoot, "tools/mo2-vfs-launcher/xedit-client.ps1");
    // Dev-sandbox fallback: only honored when the .artifacts/mo2 tree actually
    // exists. End-user clones don't have it, so this branch fails cleanly into
    // the configuration error below.
    const devSandboxLauncher = resolve(pluginRoot, ".artifacts/mo2/tools/xEdit/xEdit.exe");
    const devSandboxMoRoot = resolve(pluginRoot, ".artifacts/mo2");
    const candidateLauncher = launcherPath ?? devSandboxLauncher;
    const candidateMoRoot = moRoot ?? devSandboxMoRoot;
    statSync(candidateClient);
    statSync(candidateLauncher);
    return {
      clientScript: candidateClient,
      launcherPath: candidateLauncher,
      gameMode: gameMode ?? "Fallout4",
      moProfile,
      moRoot: candidateMoRoot,
      dataPath,
      pluginsFile,
      iKnowWhatImDoing,
    };
  } catch {
    return {
      error:
        "xedit-mcp is not configured. The harness MCP server entry needs at minimum: " +
        "BGS_MO2_ROOT (absolute path to the user's MO2 install root, i.e. the directory " +
        "containing ModOrganizer.exe). With BGS_MO2_ROOT set, the xEdit launcher defaults " +
        "to <BGS_MO2_ROOT>/tools/xEdit/xEdit.exe. " +
        "Optional env vars: BGS_XEDIT_CLIENT_SCRIPT (path to xedit-client.ps1; auto-detected " +
        "next to this MCP), BGS_XEDIT_LAUNCHER_PATH (override the xEdit.exe location), " +
        "BGS_XEDIT_GAME_MODE (e.g. 'Fallout4'), BGS_MO2_PROFILE (default 'Default'), " +
        "BGS_XEDIT_DATA_PATH (-D: flag, MO2 Data dir), BGS_XEDIT_PLUGINS_FILE (-P: flag). " +
        "Or pass these as xedit_start({ moRoot, launcherPath, gameMode, dataPath, pluginsFile, moProfile }) " +
        "overrides at runtime.",
    };
  }
}

// IMPORTANT: every parameterized tool MUST declare its `properties` and (where the
// handler enforces them) `required` explicitly. OpenCode's tool-routing layer
// inspects this JSON Schema to decide whether to forward args at all; a tool
// whose schema lacks `properties` receives `{}` on every call regardless of what
// the user/model wrote. See bgs-kb-mcp commit 15adaa7 for the parallel fix that
// landed this rule on the sibling KB MCP. Keep these schemas in sync with the
// Zod schemas in `src/tools/*.ts`. Tools with no inputs use the explicit empty
// `properties: {}` form so the schema is still introspectable.
const FORM_ID_PATTERN = "^(0x)?[0-9a-fA-F]{1,8}$";

const LAUNCH_OVERRIDE_PROPERTIES = {
  moRoot: {
    type: "string" as const,
    description:
      "Absolute path to the user's MO2 install root (the directory containing ModOrganizer.exe). " +
      "Defaults to $env:BGS_MO2_ROOT. Used for plugins.txt lookup and as the base for the launcher path default <moRoot>/tools/xEdit/xEdit.exe.",
  },
  launcherPath: {
    type: "string" as const,
    description:
      "Absolute path to xEdit.exe. Override the default <moRoot>/tools/xEdit/xEdit.exe.",
  },
  gameMode: {
    type: "string" as const,
    description: "xEdit game mode string, e.g. 'Fallout4', 'SkyrimSE', 'Starfield'.",
  },
  dataPath: {
    type: "string" as const,
    description:
      "-D: flag value: absolute path to the game Data directory. Pass MO2's <gamePath>\\Data to avoid xEdit's registry-discovered Steam path. Use backslashes; the launcher normalizes mixed slashes.",
  },
  pluginsFile: {
    type: "string" as const,
    description:
      "-P: flag value: absolute path to a custom plugins.txt. Defaults to the active MO2 profile's plugins.txt.",
  },
  moProfile: {
    type: "string" as const,
    description: "MO2 profile name, e.g. 'Default'. Defaults to $env:BGS_MO2_PROFILE or 'Default'.",
  },
  iKnowWhatImDoing: {
    type: "boolean" as const,
    description:
      "If true, launches xEdit with the -IKnowWhatImDoing flag, enabling mutating automation commands (records.create, records.copy_into, records.delete, records.mark_deleted, elements.set_value, files.create header writes, etc.). Default false; mutating intent tools (e.g. xedit_create_child_record) fast-fail with mutation_requires_iknowwhatimdoing when consent is off. Verify via xedit_session.data.consentEnabled === true after launch.",
  },
};

export const TOOL_DEFINITIONS = [
  {
    name: "xedit_status",
    description:
      "Returns the current xEdit daemon lifecycle state without blocking. status is one of 'not_started' | 'starting' | 'ready' | 'failed'. Use this to poll while waiting for a launch.",
    inputSchema: { type: "object" as const, properties: {}, additionalProperties: false },
  },
  {
    name: "xedit_start",
    description:
      "Kicks off an asynchronous xEdit daemon launch (if not already starting/ready). Returns immediately with the current status. All arguments are optional and override env-var defaults.",
    inputSchema: {
      type: "object" as const,
      properties: { ...LAUNCH_OVERRIDE_PROPERTIES },
      additionalProperties: false,
    },
  },
  {
    name: "xedit_health",
    description:
      "When the daemon is ready, sends system.ping through the named pipe to confirm it is still responsive (catches zombie daemons). Otherwise returns the same shape as xedit_status.",
    inputSchema: { type: "object" as const, properties: {}, additionalProperties: false },
  },
  {
    name: "xedit_dirty",
    description:
      "Returns xEdit's dirty state immediately. When ready: wraps session.get_dirty_state and returns { dirty, dirtyFiles, unsavedChangeCount }. Otherwise: returns the same shape as xedit_status.",
    inputSchema: { type: "object" as const, properties: {}, additionalProperties: false },
  },
  {
    name: "xedit_stop",
    description:
      "Stops the xEdit daemon and clears MCP state. Before shutdown it checks session.get_dirty_state. If there are unsaved changes and force!==true, returns code='dirty_state' with dirtyFiles instead of stopping. If the daemon is a zombie, use force:true to abandon unsaved work and clear the state.",
    inputSchema: {
      type: "object" as const,
      properties: {
        force: {
          type: "boolean" as const,
          description:
            "If true, stop even when xEdit has unsaved changes (abandons in-memory edits). Default false.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "xedit_restart",
    description:
      "Stops the current daemon (same dirty-state safety as xedit_stop) and immediately kicks off a fresh asynchronous launch. Accepts the same overrides as xedit_start plus force?: boolean. Use this to reboot with a new pluginsFile or dataPath instead of reconnecting /mcp manually.",
    inputSchema: {
      type: "object" as const,
      properties: {
        ...LAUNCH_OVERRIDE_PROPERTIES,
        force: {
          type: "boolean" as const,
          description:
            "If true, restart even when xEdit has unsaved changes (abandons in-memory edits). Default false.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "xedit_session",
    description:
      "Non-blocking. If the daemon is ready: returns gameMode, loadOrderSize, daemonPid. If not_started: auto-initiates launch. Otherwise: returns current status + hint to poll xedit_status.",
    inputSchema: { type: "object" as const, properties: {}, additionalProperties: false },
  },
  {
    name: "xedit_list_capabilities",
    description:
      "Requires the daemon to be ready. Returns the curated 49-command digest + live drift report. Fast-fails with code='not_ready' otherwise.",
    inputSchema: { type: "object" as const, properties: {}, additionalProperties: false },
  },
  {
    name: "xedit_find_record",
    description:
      "Requires the daemon to be ready. Locates records by either {file, formId} (exact override lookup) OR {editorId, signature?} (Editor ID search across the load order). Pass EXACTLY ONE search mode and OMIT the unused mode's fields entirely. DO NOT fill the unused mode with empty-string or zero placeholders — the handler will reject empty file or empty editorId. Examples: { file: 'Patch.esp', formId: '00ABCDEF' } OR { editorId: 'PlayerRef' } OR { editorId: 'PlayerRef', signature: 'NPC_' }. If both modes are supplied with valid non-empty values, {file, formId} wins. Fast-fails with code='not_ready' if the daemon is not ready.",
    // NOTE: top-level oneOf/anyOf/allOf/enum/not is forbidden by OpenAI-style
    // strict tool-schema backends; the handler-side Zod branch validation in
    // src/tools/find-record.ts is the real gate that rejects empty placeholders
    // and routes the call into the correct mode. minLength:1 on file and
    // editorId is allowed and still rejects empty-string placeholders at the
    // schema layer for clients that DO enforce that check.
    inputSchema: {
      type: "object" as const,
      properties: {
        file: {
          type: "string" as const,
          minLength: 1,
          description:
            "Plugin filename including extension, e.g. 'kinggathcreations_spaceship.esm'. Required for the {file, formId} search mode. OMIT this field in editorId mode — do not pass an empty string.",
        },
        formId: {
          type: "string" as const,
          pattern: FORM_ID_PATTERN,
          description:
            "FormID as hex, with or without 0x prefix, e.g. '0000003C' or '0x0000003C'. Up to 8 hex digits. Required for the {file, formId} search mode. OMIT this field in editorId mode — do not pass a zero placeholder.",
        },
        editorId: {
          type: "string" as const,
          minLength: 1,
          description:
            "Editor ID to search for, e.g. 'PlayerRef'. Required for the {editorId} search mode. OMIT this field in {file, formId} mode.",
        },
        signature: {
          type: "string" as const,
          description:
            "Optional 4-char record signature filter for editorId search, e.g. 'QUST', 'NPC_', 'WEAP'. Only meaningful in {editorId} mode.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "xedit_read_record",
    description:
      "Requires the daemon to be ready. Composite read of a specific record: full record + winning override + base record + conflict status. Fast-fails with code='not_ready' if the daemon is not ready.",
    inputSchema: {
      type: "object" as const,
      properties: {
        file: {
          type: "string" as const,
          description: "Plugin filename including extension, e.g. 'kinggathcreations_spaceship.esm'.",
        },
        formId: {
          type: "string" as const,
          pattern: FORM_ID_PATTERN,
          description:
            "FormID as hex, with or without 0x prefix, e.g. '0000003C' or '0x0000003C'. Up to 8 hex digits.",
        },
      },
      required: ["file", "formId"],
      additionalProperties: false,
    },
  },
  {
    name: "xedit_inspect_conflicts",
    description:
      "Requires the daemon to be ready. Conflict-audit verdict (no_conflict / itpo / itm / minor / breaking) + winning override + referenced_by listing. Fast-fails with code='not_ready' if the daemon is not ready.",
    inputSchema: {
      type: "object" as const,
      properties: {
        file: {
          type: "string" as const,
          description: "Plugin filename including extension, e.g. 'kinggathcreations_spaceship.esm'.",
        },
        formId: {
          type: "string" as const,
          pattern: FORM_ID_PATTERN,
          description:
            "FormID as hex, with or without 0x prefix, e.g. '0000003C' or '0x0000003C'. Up to 8 hex digits.",
        },
      },
      required: ["file", "formId"],
      additionalProperties: false,
    },
  },
  {
    name: "xedit_inspect_conflicts_deep",
    description:
      "Requires the daemon to be ready. Like xedit_inspect_conflicts, but also returns the new r6 child-group conflict sub-block (supports.conflictStatusChildGroup, contract 0.15) and — when includeReferences=true — chains records.references {recursive:true} (supports.referencesRecursive, contract 0.15) so the agent gets the outgoing reference tree in the same call. Use this for full Phase-15-style conflict + reference audits; use xedit_inspect_conflicts for the lighter envelope.",
    inputSchema: {
      type: "object" as const,
      properties: {
        file: {
          type: "string" as const,
          minLength: 1,
          description: "Plugin filename including extension, e.g. 'kinggathcreations_spaceship.esm'.",
        },
        formId: {
          type: "string" as const,
          pattern: FORM_ID_PATTERN,
          description:
            "FormID as hex, with or without 0x prefix, e.g. '0000003C' or '0x0000003C'. Up to 8 hex digits.",
        },
        includeReferences: {
          type: "boolean" as const,
          description:
            "If true, also call records.references {recursive:true} and attach the result under data.references. Default false.",
        },
      },
      required: ["file", "formId"],
      additionalProperties: false,
    },
  },
  {
    name: "xedit_find_records_by_pattern",
    description:
      "Requires the daemon to be ready. Wraps records.apply_filter with the r6 filter args (supports.applyFilterExtensions, contract 0.14 + 0.20 multi-pattern). At least one filter predicate is required: parentFormId, signatures, or any of *Regex / *Pattern. For multi-pattern OR, pass either a single regex string or a JSON array of strings; *Pattern and *Regex for the same logical name (editorId / displayName) are mutually exclusive.",
    inputSchema: {
      type: "object" as const,
      properties: {
        file: {
          type: "string" as const,
          minLength: 1,
          description: "Optional plugin filename to scope the filter to a single file.",
        },
        parentFormId: {
          type: "string" as const,
          pattern: FORM_ID_PATTERN,
          description:
            "Optional parent record FormID (e.g. a CELL FormID) to restrict matches to children of that record (supports.applyFilterExtensions).",
        },
        signatures: {
          type: "array" as const,
          items: { type: "string" as const, minLength: 1 },
          minItems: 1,
          description:
            "Optional list of 4-char record signatures to include, e.g. ['REFR','ACHR'].",
        },
        editorIdRegex: {
          type: "string" as const,
          description:
            "Regex against EditorID. Pass an array of strings instead of a single string to OR multiple patterns (contract 0.20 multiPattern). Mutually exclusive with editorIdPattern.",
        },
        displayNameRegex: {
          type: "string" as const,
          description:
            "Regex against display name. Multi-pattern: pass an array. Mutually exclusive with displayNamePattern.",
        },
        fullNameRegex: {
          type: "string" as const,
          description: "Regex against FULL name. Multi-pattern: pass an array.",
        },
        baseEditorIdRegex: {
          type: "string" as const,
          description: "Regex against base record's EditorID. Multi-pattern: pass an array.",
        },
        baseDisplayNameRegex: {
          type: "string" as const,
          description: "Regex against base record's display name. Multi-pattern: pass an array.",
        },
        editorIdPattern: {
          type: "string" as const,
          description:
            "Simple wildcard pattern against EditorID (no regex metachars). Mutually exclusive with editorIdRegex.",
        },
        displayNamePattern: {
          type: "string" as const,
          description:
            "Simple wildcard pattern against display name. Mutually exclusive with displayNameRegex.",
        },
        limit: {
          type: "integer" as const,
          minimum: 1,
          maximum: 10000,
          description: "Maximum matches to return (server-side cap applies).",
        },
        offset: {
          type: "integer" as const,
          minimum: 0,
          description: "Skip this many matches before returning results (pagination).",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "xedit_create_child_record",
    description:
      "MUTATING. Requires the daemon to be ready AND launched with -IKnowWhatImDoing (data.consentEnabled=true on xedit_session). Wraps records.create with the r6 parent shape (supports.createParentSpec, contract 0.16, WRLD coords extension 0.18). " +
      "Three valid parent shapes: " +
      "CELL/DIAL/QUST child = { parentFile, parentFormId, subGroup? }; " +
      "WRLD persistent child = { parentFile, parentFormId, subGroup: 'Persistent' }; " +
      "WRLD exterior child = { parentFile, parentFormId, coords: [x, y] }. " +
      "subGroup and coords are mutually exclusive. Fast-fails with code='mutation_requires_iknowwhatimdoing' if consent is not active.",
    inputSchema: {
      type: "object" as const,
      properties: {
        targetFile: {
          type: "string" as const,
          minLength: 1,
          description: "Plugin filename to create the new record in.",
        },
        signature: {
          type: "string" as const,
          minLength: 4,
          maxLength: 4,
          description:
            "4-char xEdit record signature, e.g. 'REFR', 'NPC_', 'ACHR'. Must match a supported signature for the chosen parent type.",
        },
        parent: {
          type: "object" as const,
          description:
            "Parent locator + sub-group selector. Use subGroup for CELL/DIAL/QUST/WRLD-persistent, coords for WRLD-exterior cells. Exactly one of (subGroup, coords) — never both.",
          properties: {
            parentFile: {
              type: "string" as const,
              minLength: 1,
              description: "Plugin filename of the parent record.",
            },
            parentFormId: {
              type: "string" as const,
              pattern: FORM_ID_PATTERN,
              description: "FormID of the parent record, hex with or without 0x prefix.",
            },
            subGroup: {
              type: "string" as const,
              minLength: 1,
              description:
                "Sub-group selector, e.g. 'Persistent' for a WRLD persistent child or 'Temporary' for CELL temporary children. Mutually exclusive with coords.",
            },
            coords: {
              type: "array" as const,
              items: { type: "number" as const },
              minItems: 2,
              maxItems: 2,
              description:
                "[x, y] exterior cell coordinates for a WRLD exterior child. Mutually exclusive with subGroup.",
            },
          },
          required: ["parentFile", "parentFormId"],
          additionalProperties: false,
        },
        editorId: {
          type: "string" as const,
          minLength: 1,
          description: "Optional EditorID to set on the new record.",
        },
        formData: {
          type: "object" as const,
          description: "Optional initial element payload for the new record (passed through to records.create).",
          additionalProperties: true,
        },
      },
      required: ["targetFile", "signature", "parent"],
      additionalProperties: false,
    },
  },
  {
    name: "xedit_navigate_ancestry",
    description:
      "Requires the daemon to be ready. Resolves the ancestor chain (CELL > WRLD parents, DIAL > INFO parents, QUST sub-tree, etc.) for a single record by forcing includeParents=true on records.get / records.find_by_editor_id (supports.reverseNavigation + supports.childGroupNavigation, contract 0.19 + 0.13). " +
      "Pass EITHER {file, formId} OR {editorId, signature?}. Returns a flat ancestors array, nearest-first, depth-capped at 16 per the r6 contract.",
    inputSchema: {
      type: "object" as const,
      properties: {
        file: {
          type: "string" as const,
          minLength: 1,
          description:
            "Plugin filename for {file, formId} mode. OMIT in editorId mode — do not pass an empty string.",
        },
        formId: {
          type: "string" as const,
          pattern: FORM_ID_PATTERN,
          description:
            "FormID as hex, with or without 0x prefix. OMIT in editorId mode — do not pass a zero placeholder.",
        },
        editorId: {
          type: "string" as const,
          minLength: 1,
          description:
            "EditorID for {editorId} mode. OMIT in {file, formId} mode.",
        },
        signature: {
          type: "string" as const,
          description:
            "Optional 4-char record signature filter for editorId search, e.g. 'CELL', 'REFR'. Only meaningful in {editorId} mode.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    name: "xedit_call",
    description:
      "Requires the daemon to be ready. Atomic passthrough for any of the ~49 native daemon commands, still in-harness (audit + rules + precheck still apply). " +
      "Use xedit_list_capabilities to enumerate the live command set. For multi-record read/edit work, prefer the scripts.write + scripts.run recipe: " +
      "xedit_call({ command: 'scripts.write', args: { id: 'Agent/my-procedure', source: '<Pascal>', overwrite: true } }) followed by " +
      "xedit_call({ command: 'scripts.run', args: { id: 'Agent/my-procedure', targets: [{file, formId}, ...], timeoutMs: 30000, maxStatements: 1000000 } }). " +
      "Fast-fails with code='not_ready' if the daemon is not ready.",
    inputSchema: {
      type: "object" as const,
      properties: {
        command: {
          type: "string" as const,
          description:
            "Native daemon command name, e.g. 'files.list', 'records.list', 'records.referenced_by', 'scripts.write', 'scripts.run'.",
        },
        args: {
          type: "object" as const,
          description:
            "Args object for the daemon command. Shape depends on the command — see xedit_list_capabilities. Examples: " +
            "{} for commands like files.list and system.ping; " +
            "{ file: 'kinggathcreations_spaceship.esm', signature: 'QUST' } for records.list; " +
            "{ file, formId } for records.get / .winning_override / .base_record / .conflict_status / .referenced_by / .children.",
          additionalProperties: true,
        },
      },
      required: ["command"],
      additionalProperties: false,
    },
  },
];

// State machine
type LaunchState =
  | { status: "not_started" }
  | { status: "starting"; startedAt: number }
  | { status: "ready"; pid: number; since: number }
  | { status: "failed"; error: string; at: number };

// Helper to build the MCP CallTool response. Return type is loose so the
// SDK's expected ServerResult shape is satisfied without import-coupling.
function jsonResult(body: unknown, isError = false) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(body) }],
    isError,
  };
}

function statusFields(state: LaunchState, daemon: LaunchedDaemon | null): Record<string, unknown> {
  const out: Record<string, unknown> = { status: state.status };
  if (state.status === "starting") {
    out.startedAt = state.startedAt;
    out.elapsedSeconds = Math.round((Date.now() - state.startedAt) / 1000);
  } else if (state.status === "ready") {
    out.pid = state.pid;
    out.readySince = state.since;
    if (daemon) out.daemonPid = daemon.pid;
  } else if (state.status === "failed") {
    out.error = state.error;
    out.failedAt = state.at;
  }
  return out;
}

export async function main(): Promise<void> {
  const server = new Server(
    { name: "xedit-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  let state: LaunchState = { status: "not_started" };
  let toolset: ServerToolset | null = null;
  let daemonRef: LaunchedDaemon | null = null;
  let launchGeneration = 0;

  function clearRuntimeState(next: LaunchState = { status: "not_started" }) {
    launchGeneration += 1;
    state = next;
    toolset = null;
    daemonRef = null;
  }

  async function getDirtyState() {
    if (state.status !== "ready" || !daemonRef) {
      return {
        ok: false as const,
        body: {
          ok: true,
          tool: "xedit_dirty",
          data: { ...statusFields(state, daemonRef), responsive: false },
          hint:
            state.status === "not_started"
              ? "Daemon not started. Call xedit_start."
              : state.status === "starting"
                ? "Daemon still starting. Poll xedit_status."
                : "Daemon failed to start; inspect data.error.",
        },
      };
    }

    try {
      const env = await daemonRef.adapter.call({ command: "session.get_dirty_state", args: {} });
      if (!env.ok) {
        const code = env.error?.code ?? "daemon_error";
        const message = env.error?.message ?? "session.get_dirty_state failed";
        return {
          ok: false as const,
          body: {
            ok: false,
            tool: "xedit_dirty",
            code,
            summary: message,
            hint: message,
          },
        };
      }

      const result = (env.result ?? {}) as {
        dirty?: unknown;
        dirtyFiles?: unknown;
        unsavedChangeCount?: unknown;
      };
      const dirtyFiles = Array.isArray(result.dirtyFiles)
        ? result.dirtyFiles.filter((x): x is string => typeof x === "string")
        : [];
      const unsavedChangeCount =
        typeof result.unsavedChangeCount === "number" && Number.isFinite(result.unsavedChangeCount)
          ? result.unsavedChangeCount
          : dirtyFiles.length;

      return {
        ok: true as const,
        body: {
          ok: true,
          tool: "xedit_dirty",
          data: {
            ...statusFields(state, daemonRef),
            dirty: result.dirty === true,
            dirtyFiles,
            unsavedChangeCount,
          },
        },
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        ok: false as const,
        body: {
          ok: false,
          tool: "xedit_dirty",
          code: "daemon_error",
          summary: msg,
          hint: msg,
        },
      };
    }
  }

  function kickoffLaunch(overrides: LaunchOverrides = {}): { kicked: boolean; reason?: string } {
    if (state.status === "starting") return { kicked: false, reason: "already_starting" };
    if (state.status === "ready") return { kicked: false, reason: "already_ready" };

    const opts = resolveLaunchOpts(overrides);
    if ("error" in opts) {
      clearRuntimeState({ status: "failed", error: opts.error, at: Date.now() });
      return { kicked: false, reason: opts.error };
    }

    const launchGen = ++launchGeneration;
    state = { status: "starting", startedAt: Date.now() };

    // Fire-and-forget: this promise resolves in the background while tool calls
    // return immediately. State is mutated in the closures below.
    void (async () => {
      try {
        const daemon = await launchDaemon(opts);
        if (launchGen !== launchGeneration) {
          try {
            await daemon.stop();
          } catch {
            /* best effort */
          }
          return;
        }
        daemonRef = daemon;
        toolset = buildServerToolset({
          adapter: daemon.adapter,
          sessionId: `mcp-${process.pid}-${Date.now()}`,
          daemonPid: daemon.pid,
        });
        state = { status: "ready", pid: daemon.pid, since: Date.now() };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (launchGen !== launchGeneration) {
          return;
        }
        state = { status: "failed", error: msg, at: Date.now() };
        daemonRef = null;
        toolset = null;
      }
    })();

    return { kicked: true };
  }

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS,
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const name = req.params.name;
    const args = (req.params.arguments ?? {}) as Record<string, unknown>;

    // ---- LIFECYCLE / HEALTH tools (always non-blocking) ----

    if (name === "xedit_status") {
      return jsonResult({ ok: true, tool: name, data: statusFields(state, daemonRef) });
    }

    if (name === "xedit_start") {
      // Extract override args (all optional). Unknown extra keys ignored.
      const overrides: LaunchOverrides = {
        moRoot: typeof args.moRoot === "string" ? args.moRoot : undefined,
        launcherPath: typeof args.launcherPath === "string" ? args.launcherPath : undefined,
        gameMode: typeof args.gameMode === "string" ? args.gameMode : undefined,
        dataPath: typeof args.dataPath === "string" ? args.dataPath : undefined,
        pluginsFile: typeof args.pluginsFile === "string" ? args.pluginsFile : undefined,
        iKnowWhatImDoing: args.iKnowWhatImDoing === true ? true : undefined,
        moProfile: typeof args.moProfile === "string" ? args.moProfile : undefined,
      };
      const kick = kickoffLaunch(overrides);
      const body = {
        ok: true,
        tool: name,
        data: statusFields(state, daemonRef),
        kicked: kick.kicked,
        message: kick.kicked
          ? "Daemon launch initiated in the background. Poll xedit_status until status='ready'."
          : kick.reason === "already_ready"
            ? "Daemon is already ready."
            : kick.reason === "already_starting"
              ? "Daemon launch already in progress. Poll xedit_status until status='ready'."
              : (kick.reason ?? "Launch could not be initiated."),
      };
      return jsonResult(body);
    }

    if (name === "xedit_health") {
      if (state.status !== "ready" || !daemonRef) {
        return jsonResult({
          ok: true,
          tool: name,
          data: { ...statusFields(state, daemonRef), responsive: false },
          hint: state.status === "not_started"
            ? "Daemon not started. Call xedit_start."
            : state.status === "starting"
              ? "Daemon still starting. Poll xedit_status."
              : "Daemon failed to start; inspect data.error.",
        });
      }
      try {
        const ping = await daemonRef.adapter.call({ command: "system.ping", args: {} });
        return jsonResult({
          ok: true,
          tool: name,
          data: {
            ...statusFields(state, daemonRef),
            responsive: ping.ok === true,
            pingEnvelope: ping,
          },
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return jsonResult({
          ok: true,
          tool: name,
          data: {
            ...statusFields(state, daemonRef),
            responsive: false,
            pingError: msg,
          },
          hint: "Daemon claimed ready but did not respond to system.ping. It may be a zombie; consider restarting MO2.",
        });
      }
    }

    if (name === "xedit_dirty") {
      const dirty = await getDirtyState();
      return jsonResult(dirty.body, !dirty.body.ok);
    }

    if (name === "xedit_stop") {
      const force = args.force === true;

      if (state.status === "not_started") {
        return jsonResult({
          ok: true,
          tool: name,
          data: statusFields(state, daemonRef),
          message: "Daemon already stopped.",
        });
      }

      if (state.status === "ready") {
        const dirty = await getDirtyState();
        if (dirty.ok) {
          const data = dirty.body.data as { dirty?: boolean; dirtyFiles?: string[]; unsavedChangeCount?: number };
          if (data.dirty && !force) {
            return jsonResult({
              ok: false,
              tool: name,
              code: "dirty_state",
              summary: "xEdit has unsaved changes. Refusing to stop without force=true.",
              data,
              hint: "Either save the dirty files first, or call xedit_stop({ force: true }) to abandon the in-memory edits.",
            }, true);
          }
        }
      }

      const current = daemonRef;
      clearRuntimeState();
      if (current) {
        try {
          await current.stop();
        } catch {
          /* best effort */
        }
      }
      return jsonResult({
        ok: true,
        tool: name,
        data: { status: "not_started" },
        message: "Daemon stopped and MCP runtime state cleared.",
      });
    }

    if (name === "xedit_restart") {
      const force = args.force === true;
      const overrides: LaunchOverrides = {
        moRoot: typeof args.moRoot === "string" ? args.moRoot : undefined,
        launcherPath: typeof args.launcherPath === "string" ? args.launcherPath : undefined,
        gameMode: typeof args.gameMode === "string" ? args.gameMode : undefined,
        dataPath: typeof args.dataPath === "string" ? args.dataPath : undefined,
        pluginsFile: typeof args.pluginsFile === "string" ? args.pluginsFile : undefined,
        iKnowWhatImDoing: args.iKnowWhatImDoing === true ? true : undefined,
        moProfile: typeof args.moProfile === "string" ? args.moProfile : undefined,
      };

      if (state.status === "ready") {
        const dirty = await getDirtyState();
        if (dirty.ok) {
          const data = dirty.body.data as { dirty?: boolean; dirtyFiles?: string[]; unsavedChangeCount?: number };
          if (data.dirty && !force) {
            return jsonResult({
              ok: false,
              tool: name,
              code: "dirty_state",
              summary: "xEdit has unsaved changes. Refusing to restart without force=true.",
              data,
              hint: "Either save the dirty files first, or call xedit_restart({ force: true, ... }) to abandon the in-memory edits and relaunch with the new overrides.",
            }, true);
          }
        }
      }

      const current = daemonRef;
      clearRuntimeState();
      if (current) {
        try {
          await current.stop();
        } catch {
          /* best effort */
        }
      }
      const kick = kickoffLaunch(overrides);
      return jsonResult({
        ok: true,
        tool: name,
        data: statusFields(state, daemonRef),
        kicked: kick.kicked,
        message: kick.kicked
          ? "Daemon restart initiated in the background. Poll xedit_status until status='ready'."
          : (kick.reason ?? "Restart could not be initiated."),
      });
    }

    // ---- DOMAIN tools ----

    if (name === "xedit_session") {
      if (state.status === "ready" && toolset) {
        try {
          const env = await toolset.invoke("xedit_session", args);
          return jsonResult(env, !env.ok);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          return jsonResult({ ok: false, tool: name, code: "internal_error", summary: msg, hint: msg }, true);
        }
      }
      // Not ready: auto-kick the launch if not yet started, then surface status.
      if (state.status === "not_started") {
        kickoffLaunch();
      }
      return jsonResult({
        ok: true,
        tool: name,
        data: statusFields(state, daemonRef),
        hint: state.status === "failed"
          ? "Launch failed; inspect data.error. Call xedit_start to retry."
          : "Daemon not ready yet; poll xedit_status until status='ready'.",
      });
    }

    // Other domain tools require ready
    if (state.status !== "ready" || !toolset) {
      return jsonResult({
        ok: false,
        tool: name,
        code: "not_ready",
        summary: `Daemon is not ready (status='${state.status}').`,
        data: statusFields(state, daemonRef),
        hint: state.status === "not_started"
          ? "Call xedit_start, then poll xedit_status until status='ready'."
          : state.status === "starting"
            ? "Launch in progress. Poll xedit_status."
            : "Launch failed; inspect data.error. Call xedit_start to retry.",
      }, true);
    }

    try {
      const env = await toolset.invoke(name, args);
      return jsonResult(env, !env.ok);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResult({ ok: false, tool: name, code: "internal_error", summary: msg, hint: msg }, true);
    }
  });

  const shutdown = async (signal: string) => {
    process.stderr.write(`xedit-mcp received ${signal}, shutting down...\n`);
    if (daemonRef) {
      try { await daemonRef.stop(); } catch { /* best effort */ }
    }
    process.exit(0);
  };
  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  await server.connect(new StdioServerTransport());
}

// Detect "invoked as the main entry" cross-platform. On Windows, naive string
// compare against `file://${argv[1]}` fails because of backslash + slash-count
// differences. Use pathToFileURL to normalize. (See earlier P5 bugfix commit.)
const invokedAsMain = (() => {
  const argv = process.argv[1];
  if (!argv) return false;
  try {
    return import.meta.url === pathToFileURL(argv).href;
  } catch {
    return false;
  }
})();

if (invokedAsMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
