/**
 * mo2_assets_resolve — T1 single-path resolution via sidecar.
 *
 * Returns winner mod + provider chain for one virtual path.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
const inputSchema = z.object({
    profile: z.string().default("Default"),
    virtual_path: z.string(),
});
registerTool({
    name: "mo2_assets_resolve",
    tier: "T1",
    description: "Resolve a virtual path (e.g. 'Data/textures/foo.dds') to winner mod + provider chain via sidecar.",
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
        const result = await ctx.sidecar.call("assets.resolve_file", {
            profile_dir: profileDir,
            virtual_path: args.virtual_path,
        });
        return { ok: true, result, error: null };
    },
});
