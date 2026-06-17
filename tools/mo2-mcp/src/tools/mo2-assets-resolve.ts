/**
 * mo2_assets_resolve — T1 single-path resolution via sidecar.
 *
 * Returns winner mod + provider chain for one virtual path.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): virtual_path gains .min(1).
const inputSchema = z.object({
  profile: z.string().default("Default"),
  virtual_path: z.string().min(1),
});

registerTool({
  name: "mo2_assets_resolve",
  tier: "T1",
  description:
    "Resolve a virtual path (e.g. 'Data/textures/foo.dds') to winner mod + provider chain via sidecar.",
  inputSchema,
  handler: async (args, ctx) => {
    const bound = requireBoundContext(ctx);
    if (!bound.sidecar) {
      return {
        ok: false,
        error: { code: "sidecar_not_ready", message: "Python sidecar not available" },
      };
    }
    const profile = (args.profile as string) ?? "Default";
    const profileDir = join(bound.config.mo2Root, "profiles", profile);
    const result = await bound.sidecar.call("assets.resolve_file", {
      profile_dir: profileDir,
      virtual_path: args.virtual_path,
    });
    return { ok: true, result, error: null };
  },
});
