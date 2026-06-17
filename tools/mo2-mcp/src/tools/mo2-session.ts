/**
 * mo2_session — lazy-bind lifecycle tool.
 *
 * Shapes:
 *   {}                       -> read current BindingSnapshot (introspection)
 *   { mo2Root, profile? }    -> bind/rebind to that MO2 root
 *   { unbind: true }         -> cleanup active binding and return unbound snapshot
 *
 * BUG-7 fix (2026-06-17): the schema must accept fully-empty args `{}` as the
 * canonical introspection form. The previous schema declared the optional
 * string fields with `z.string().min(1).optional()`, which produced a wire
 * JSON Schema with `minLength: 1` on optional fields. Some OpenCode tool-call
 * surfaces (and LLM-side tool emitters) treat that as "field must be present
 * and non-empty" and refuse to emit `mo2_session({})`, making the documented
 * introspection contract unreachable through the function-call surface.
 *
 * The fix is to drop `.min(1)`: every field stays optional, the wire schema
 * has no minimum-length constraint, and the handler already treats blank /
 * whitespace-only `mo2Root` as introspection (via `.trim()` below). Real
 * binds still pass a non-empty path; agents who accidentally send an empty
 * string get the introspection snapshot back rather than a confusing
 * invalid_arguments envelope.
 *
 * This is intentionally NOT the BUG-10 pattern — `mo2_session` is the
 * lifecycle introspection tool and its emptiness is the contract. For
 * required-field tools (toggle/create/rename/etc.), see BUG-10's `.min(1)`
 * enforcement.
 */
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

const inputSchema = z.object({
  mo2Root: z.string().optional(),
  profile: z.string().optional(),
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
