/**
 * mo2_session — lazy-bind lifecycle tool.
 *
 * Shapes:
 *   {}                       -> read current BindingSnapshot
 *   { mo2Root, profile? }    -> bind/rebind to that MO2 root
 *   { unbind: true }         -> cleanup active binding and return unbound snapshot
 */
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

const inputSchema = z.object({
  mo2Root: z.string().min(1).optional(),
  profile: z.string().min(1).optional(),
  unbind: z.boolean().optional(),
});

registerTool({
  name: "mo2_session",
  tier: "T1",
  description:
    "Inspect or change the MO2 MCP lazy binding. Call with no args to inspect, {mo2Root, profile?} to bind/rebind, or {unbind:true} to unbind.",
  inputSchema,
  handler: async (args, ctx) => {
    if (args.unbind === true) {
      await ctx.binding.unbind();
      return { ok: true, snapshot: bindingSnapshot(ctx) };
    }

    if (typeof args.mo2Root === "string" && args.mo2Root.trim()) {
      const snapshot = await ctx.binding.bind({
        mo2Root: args.mo2Root,
        profile: typeof args.profile === "string" && args.profile.trim() ? args.profile : undefined,
      });
      return { ok: true, snapshot };
    }

    return { ok: true, snapshot: bindingSnapshot(ctx) };
  },
});
