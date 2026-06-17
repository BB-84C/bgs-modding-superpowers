/**
 * mo2_configure_executable — T3 edit ModOrganizer.ini [customExecutables].
 *
 * This is intentionally offline-only while MO2 is closed. MO2 rewrites
 * ModOrganizer.ini on exit, so direct INI edits while it is running are unsafe.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { readMoIni, type MoIniCustomExecutable } from "../mo-ini.js";
import { atomicWriteText } from "../atomic.js";
import { detectMo2Running } from "../detection.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

const ExecutableEntrySchema = z.object({
  title: z.string(),
  binary: z.string(),
  arguments: z.string().default(""),
  workingDirectory: z.string().default(""),
  steamAppID: z.string().default(""),
  ownicon: z.boolean().default(false),
  hide: z.boolean().default(false),
  toolbar: z.boolean().optional(),
  minimizeToSystemTray: z.boolean().optional(),
});

const ExecutableUpdatesSchema = z.object({
  title: z.string().optional(),
  binary: z.string().optional(),
  arguments: z.string().optional(),
  workingDirectory: z.string().optional(),
  steamAppID: z.string().optional(),
  ownicon: z.boolean().optional(),
  hide: z.boolean().optional(),
  toolbar: z.boolean().optional(),
  minimizeToSystemTray: z.boolean().optional(),
});

const planSchema = z.discriminatedUnion("action", [
  z.object({
    mode: z.literal("plan"),
    action: z.literal("add"),
    entry: ExecutableEntrySchema,
  }),
  z.object({
    mode: z.literal("plan"),
    action: z.literal("edit"),
    title: z.string(),
    updates: ExecutableUpdatesSchema,
  }),
  z.object({
    mode: z.literal("plan"),
    action: z.literal("remove"),
    title: z.string(),
  }),
]);

const inputSchema = z.union([
  planSchema,
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);

type ExecutableEntry = z.infer<typeof ExecutableEntrySchema>;
type ExecutableUpdates = z.infer<typeof ExecutableUpdatesSchema>;

const ENTRY_KEY_ORDER = [
  "arguments",
  "binary",
  "hide",
  "ownicon",
  "steamAppID",
  "title",
  "toolbar",
  "workingDirectory",
  "minimizeToSystemTray",
] as const;

async function _assertMo2Closed(mo2Root: string): Promise<void> {
  const det = await detectMo2Running({ mo2Root });
  if (det.processRunning) {
    throw new Error("mo2_running_ini_unsafe: close MO2 first or use mo2_switch_profile then this tool");
  }
}

/**
 * Keys whose values are filesystem paths and must be written with forward
 * slashes. MO2 itself writes these with forward slashes; Qt QSettings on
 * subsequent read treats `\W`, `\S`, etc. as undefined escape sequences and
 * strips the leading backslash, corrupting paths like
 * `C:\Windows\System32\notepad.exe` into `C:indowsystem32\notepad.exe`.
 *
 * `arguments` is intentionally NOT in this set: command-line arguments may
 * embed verbatim Windows path literals that the launched program parses on
 * its own (e.g. `-D "D:\Games\Fallout 4"`); the caller is responsible for
 * whatever quoting/escaping that program needs, and we must round-trip
 * those bytes verbatim.
 *
 * `title` is also NOT in this set: titles are arbitrary user-facing labels
 * and not path-typed.
 */
const PATH_KEYS = new Set(["binary", "workingDirectory"]);

export function _serializeValue(key: string, value: string | boolean): string {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (PATH_KEYS.has(key) && value.includes("\\")) {
    return value.replace(/\\/g, "/");
  }
  return value;
}

function _serializeCustomExecutables(
  entries: MoIniCustomExecutable[],
  newline: string,
  trailingBlank: boolean,
): string {
  const lines = ["[customExecutables]", `size=${entries.length}`];
  entries.forEach((entry, index) => {
    const prefix = `${index + 1}\\`;
    const seen = new Set<string>();
    for (const key of ENTRY_KEY_ORDER) {
      const value = entry[key as keyof MoIniCustomExecutable];
      if (value === undefined) continue;
      lines.push(`${prefix}${key}=${_serializeValue(key, value)}`);
      seen.add(key);
    }
    for (const [key, value] of Object.entries(entry)) {
      if (seen.has(key) || value === undefined) continue;
      if (typeof value === "string" || typeof value === "boolean") {
        lines.push(`${prefix}${key}=${_serializeValue(key, value)}`);
      }
    }
  });
  if (trailingBlank) lines.push("");
  return lines.join(newline);
}

export function _rewriteCustomExecutables(
  raw: string,
  range: [number, number] | undefined,
  entries: MoIniCustomExecutable[],
): string {
  const newline = raw.includes("\r\n") ? "\r\n" : "\n";
  const lines = raw.split(/\r?\n/);
  if (!range) {
    const prefix = raw.endsWith("\n") || raw.length === 0 ? raw : `${raw}${newline}`;
    return `${prefix}${_serializeCustomExecutables(entries, newline, false)}${newline}`;
  }
  const trailingBlank = lines[range[1]] === "";
  const section = _serializeCustomExecutables(entries, newline, trailingBlank).split(newline);
  return [...lines.slice(0, range[0]), ...section, ...lines.slice(range[1] + 1)].join(newline);
}

function _withDefaults(entry: ExecutableEntry): MoIniCustomExecutable {
  return {
    title: entry.title,
    binary: entry.binary,
    arguments: entry.arguments,
    workingDirectory: entry.workingDirectory,
    steamAppID: entry.steamAppID,
    ownicon: entry.ownicon,
    hide: entry.hide,
    ...(entry.toolbar === undefined ? {} : { toolbar: entry.toolbar }),
    ...(entry.minimizeToSystemTray === undefined ? {} : { minimizeToSystemTray: entry.minimizeToSystemTray }),
  };
}

const handler: PlanApplyHandler = {
  toolName: "mo2_configure_executable",
  async buildPlan(args, ctx) {
    const bound = requireBoundContext(ctx);
    await _assertMo2Closed(bound.config.mo2Root);
    const iniPath = join(bound.config.mo2Root, "ModOrganizer.ini");
    const ini = await readMoIni(iniPath);
    let diff: string;
    if (args.action === "add") {
      const entry = args.entry as ExecutableEntry;
      if (ini.customExecutables.some((existing) => existing.title === entry.title)) {
        throw new Error(`title_exists: ${entry.title}`);
      }
      diff = `+ ${entry.title} → ${entry.binary}`;
    } else if (args.action === "edit") {
      const title = args.title as string;
      if (!ini.customExecutables.some((entry) => entry.title === title)) {
        throw new Error(`title_not_found: ${title}`);
      }
      diff = `~ ${title}: ${JSON.stringify(args.updates)}`;
    } else {
      const title = args.title as string;
      if (!ini.customExecutables.some((entry) => entry.title === title)) {
        throw new Error(`title_not_found: ${title}`);
      }
      diff = `- ${title}`;
    }
    return {
      diff,
      affectedFiles: [iniPath],
      targets: [{ path: iniPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    const iniPath = join(bound.config.mo2Root, "ModOrganizer.ini");
    const ini = await readMoIni(iniPath);
    let entries: MoIniCustomExecutable[] = ini.customExecutables.map((entry) => ({ ...entry }));
    if (plan.args.action === "add") {
      entries.push(_withDefaults(plan.args.entry as ExecutableEntry));
    } else if (plan.args.action === "edit") {
      const title = plan.args.title as string;
      const idx = entries.findIndex((entry) => entry.title === title);
      if (idx < 0) throw new Error(`title_not_found: ${title}`);
      entries[idx] = { ...entries[idx], ...(plan.args.updates as ExecutableUpdates) };
    } else if (plan.args.action === "remove") {
      const title = plan.args.title as string;
      entries = entries.filter((entry) => entry.title !== title);
    } else {
      throw new Error(`unknown_action: ${String(plan.args.action)}`);
    }

    const newText = _rewriteCustomExecutables(
      ini.raw,
      ini.sectionRanges.get("customExecutables"),
      entries,
    );
    await atomicWriteText(iniPath, newText);
    return { action: plan.args.action as string, executables_count: entries.length };
  },
};

registerTool({
  name: "mo2_configure_executable",
  tier: "T3",
  description:
    "Add/edit/remove a customExecutables entry. Refuses if MO2 running. Atomic INI rewrite preserves other sections.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
