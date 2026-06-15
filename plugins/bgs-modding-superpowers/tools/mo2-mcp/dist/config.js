/**
 * Configuration loader for the MO2 MCP server.
 *
 * Loads from two sources at startup (no hot-reload — oracle §3.3):
 * 1. BGS_MO2_ROOT env var → mo2Root (required)
 * 2. <mo2Root>/.mo2-mcp.json → permission_ceiling, allowed_profiles, deny, ...
 * 3. BGS_MO2_PERMISSION_CEILING env var → permission_ceiling override
 *
 * Defaults applied via Zod when .mo2-mcp.json missing or fields absent.
 */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
export const ConfigSchema = z
    .object({
    permission_ceiling: z
        .enum(["read-only", "metadata-editable", "full-control"])
        .default("metadata-editable"),
    allowed_profiles: z.array(z.string()).default(["Default"]),
    deny: z.array(z.string()).default(["Stock Game/Data/**"]),
    snapshot_root: z.string().default(".mo2-mcp/snapshots"),
    audit_root: z.string().default(".mo2-mcp/audit"),
})
    .strict();
export async function loadConfig(opts) {
    if (!opts.mo2Root) {
        throw new Error("BGS_MO2_ROOT not set");
    }
    let raw = {};
    try {
        const configPath = join(opts.mo2Root, ".mo2-mcp.json");
        const text = await readFile(configPath, "utf8");
        raw = JSON.parse(text);
    }
    catch (e) {
        const maybeNodeError = e;
        if (maybeNodeError.code !== "ENOENT") {
            const message = e instanceof Error ? e.message : String(e);
            process.stderr.write(`[config] failed to read .mo2-mcp.json: ${message}\n`);
        }
    }
    const envPermissionCeiling = process.env.BGS_MO2_PERMISSION_CEILING;
    const rawWithEnv = envPermissionCeiling
        ? {
            ...(raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {}),
            permission_ceiling: envPermissionCeiling,
        }
        : raw;
    const parsed = ConfigSchema.parse(rawWithEnv);
    return {
        mo2Root: opts.mo2Root,
        permissionCeiling: parsed.permission_ceiling,
        allowedProfiles: parsed.allowed_profiles,
        deny: parsed.deny,
        snapshotRoot: join(opts.mo2Root, parsed.snapshot_root),
        auditRoot: join(opts.mo2Root, parsed.audit_root),
    };
}
