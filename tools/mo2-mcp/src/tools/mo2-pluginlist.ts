/**
 * mo2_pluginlist — T1 native TS read of plugins.txt.
 *
 * `*` prefix = enabled (FO4/SSE convention, NOT charrdge's inverted polarity).
 * Optional enrich=true: when broker live, adds masters/load_order/origin/flags
 * via mobase IPluginList.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { readProfile } from "../profile-reader.js";

const inputSchema = z.object({
  profile: z.string().default("Default"),
  enrich: z.boolean().default(false),
});

registerTool({
  name: "mo2_pluginlist",
  tier: "T1",
  description:
    "Read plugins.txt. Returns plugins with name + enabled (* = enabled per MO2/FO4 convention). Optional broker enrich adds masters/load_order/origin/flags.",
  inputSchema,
  handler: async (args, ctx) => {
    const profile = (args.profile as string) ?? "Default";
    const profileDir = join(ctx.config.mo2Root, "profiles", profile);
    const p = await readProfile(profileDir);
    let plugins: Array<Record<string, unknown>> = p.plugins.map((pl) => ({ ...pl }));
    if (args.enrich && ctx.pipeClient) {
      try {
        const resp = await ctx.pipeClient.call("plugins.list", {});
        if (resp.ok && resp.result && typeof resp.result === "object") {
          const livePlugins = (resp.result as { plugins?: Array<{ name: string }> }).plugins ?? [];
          const liveMap = new Map<string, Record<string, unknown>>();
          for (const lp of livePlugins) liveMap.set(lp.name, lp);
          plugins = plugins.map((pl) => ({ ...pl, ...(liveMap.get(pl.name as string) ?? {}) }));
        }
      } catch {
        // Silent fail
      }
    }
    return {
      ok: true,
      result: { profile, plugins, plugin_count: plugins.length },
      error: null,
    };
  },
});
