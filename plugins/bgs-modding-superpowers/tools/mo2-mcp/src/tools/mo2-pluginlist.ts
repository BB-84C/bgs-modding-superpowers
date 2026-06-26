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
import { requireBoundContext } from "../binding.js";

const inputSchema = z.object({
  profile: z.string().default("Default"),
  enrich: z.boolean().default(false),
});

type PluginRow = Record<string, unknown> & {
  name: string;
  enabled: boolean;
  isComment?: boolean;
  priority?: number;
  gui_rank?: number;
  load_order_role?: "loads_first_lowest_precedence" | "loads_last_highest_precedence" | "intermediate";
};

function enrichGuiFields(plugins: PluginRow[]): PluginRow[] {
  const realPluginCount = plugins.filter((pl) => !pl.isComment).length;
  let offlineRank = 0;

  return plugins.map((pl) => {
    if (pl.isComment) return pl;

    offlineRank += 1;
    const guiRank = typeof pl.priority === "number" ? pl.priority + 1 : offlineRank;
    const loadOrderRole =
      guiRank === 1
        ? "loads_first_lowest_precedence"
        : guiRank === realPluginCount
          ? "loads_last_highest_precedence"
          : "intermediate";

    return {
      ...pl,
      gui_rank: guiRank,
      load_order_role: loadOrderRole,
    };
  });
}

registerTool({
  name: "mo2_pluginlist",
  tier: "T1",
  description:
    "Read plugins.txt. Returns plugins with name + enabled (* = enabled per MO2/FO4 convention). Optional broker enrich adds masters/load_order/origin/flags.",
  inputSchema,
  handler: async (args, ctx) => {
    const bound = requireBoundContext(ctx);
    const profile = (args.profile as string) ?? "Default";
    const profileDir = join(bound.config.mo2Root, "profiles", profile);
    const p = await readProfile(profileDir);
    let plugins: PluginRow[] = p.plugins.map((pl) => ({ ...pl }));
    if (args.enrich && bound.pipeClient) {
      try {
        const resp = await bound.pipeClient.call("plugins.list", {});
        if (resp.ok && resp.result && typeof resp.result === "object") {
          const livePlugins = (resp.result as { plugins?: Array<{ name: string }> }).plugins ?? [];
          const liveMap = new Map<string, Record<string, unknown>>();
          for (const lp of livePlugins) liveMap.set(lp.name, lp);
          plugins = plugins.map((pl) => ({ ...pl, ...(liveMap.get(pl.name) ?? {}) }));
        }
      } catch {
        // Silent fail
      }
    }
    plugins = enrichGuiFields(plugins);
    return {
      ok: true,
      result: {
        profile,
        plugins,
        plugin_count: plugins.length,
        _meta: {
          array_order: "plugins_txt_forward_order_matches_gui",
          array_order_note:
            "First entry is at TOP of MO2 GUI plugins panel (loaded first = lowest precedence). Last entry is at BOTTOM of GUI (loaded last = WINS all plugin conflicts).",
          priority_vs_load_order:
            "When enriched, 'priority' = position in plugins.txt; 'load_order' = effective post-sort load index (these differ when ESL/light/master plugins interleave). Agents reasoning about precedence should use 'load_order'.",
          enabled_marker:
            "Asterisk (*) prefix in plugins.txt means enabled. plugin_count includes the comment header entry as a synthetic isComment:true row.",
        },
      },
      error: null,
    };
  },
});
