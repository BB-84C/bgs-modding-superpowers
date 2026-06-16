/**
 * mo2_assets_conflicts — T1 sidecar-backed conflict listing with bounded output.
 *
 * max_results default 10000; sidecar returns truncated flag.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.object({
    profile: z.string().default("Default"),
    max_results: z.number().int().min(1).max(50000).default(10000),
    path_prefix: z.string().optional(),
});
registerTool({
    name: "mo2_assets_conflicts",
    tier: "T1",
    description: "List file conflicts via Python sidecar. Bounded output (max_results, default 10000). Returns conflicts array + total_count + truncated flag.",
    inputSchema,
    handler: async (args, ctx) => {
        const bound = requireBoundContext(ctx);
        if (!bound.sidecar) {
            return {
                ok: false,
                error: { code: "sidecar_not_ready", message: "Python sidecar not available" },
            };
        }
        const profile = args.profile ?? "Default";
        const profileDir = join(bound.config.mo2Root, "profiles", profile);
        const result = await bound.sidecar.call("assets.conflicts", {
            profile_dir: profileDir,
            max_results: args.max_results,
            path_prefix: args.path_prefix,
        });
        return { ok: true, result, error: null };
    },
});
