/**
 * mo2_assets_summary — T1 sidecar-backed counts.
 *
 * Delegates to the Python sidecar's `assets.summary` JSON-RPC method
 * (S1b sidecar wraps mo2_assets_engine).
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
const inputSchema = z.object({
    profile: z.string().default("Default"),
});
registerTool({
    name: "mo2_assets_summary",
    tier: "T1",
    description: "Summary counts (mod_count, enabled_mod_count, game) via Python sidecar (mo2_assets_engine).",
    inputSchema,
    handler: async (args, ctx) => {
        if (!ctx.sidecar) {
            return {
                ok: false,
                error: { code: "sidecar_not_ready", message: "Python sidecar not available" },
            };
        }
        const profile = args.profile ?? "Default";
        const profileDir = join(ctx.config.mo2Root, "profiles", profile);
        const result = await ctx.sidecar.call("assets.summary", { profile_dir: profileDir });
        return { ok: true, result, error: null };
    },
});
