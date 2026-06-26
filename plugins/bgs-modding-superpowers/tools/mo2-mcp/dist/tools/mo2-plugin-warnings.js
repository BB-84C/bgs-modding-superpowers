import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { requireBoundContext } from "../binding.js";
import { pollPluginWarnings } from "../plugin-warnings.js";
const inputSchema = z.object({
    names: z.array(z.string().min(1)).optional(),
}).strict();
registerTool({
    name: "mo2_plugin_warnings",
    tier: "T1",
    description: "Poll MO2 for missing-master dependency warnings on enabled plugins. " +
        "Mirrors the GUI's red '!' indicator (Missing Masters tooltip). " +
        "Read-only. With names: scan only those plugins. Without: scan all enabled.",
    inputSchema,
    handler: async (args, ctx) => {
        const bound = requireBoundContext(ctx);
        if (!bound.pipeClient) {
            return {
                ok: true,
                hasWarnings: false,
                pluginWarnings: {
                    warnings: [],
                    scannedCount: 0,
                    enabledCount: 0,
                    pollFailed: "live_broker_required",
                },
            };
        }
        const result = await pollPluginWarnings(bound.pipeClient, args.names);
        return {
            ok: true,
            hasWarnings: result.warnings.length > 0,
            pluginWarnings: result,
        };
    },
});
