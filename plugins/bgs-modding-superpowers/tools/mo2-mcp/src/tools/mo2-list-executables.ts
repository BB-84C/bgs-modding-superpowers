/**
 * mo2_list_executables — T1 read ModOrganizer.ini customExecutables.
 *
 * Returns the array of {title, binary, arguments, workingDirectory, ...} as
 * parsed by readMoIni().
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";

const inputSchema = z.object({});

registerTool({
  name: "mo2_list_executables",
  tier: "T1",
  description:
    "List configured customExecutables from ModOrganizer.ini (title, binary, arguments, workingDirectory, steamAppID, ownicon, hide, ...).",
  inputSchema,
  handler: async (_args, ctx) => {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    return {
      ok: true,
      result: {
        executables: ini.customExecutables,
        count: ini.customExecutables.length,
      },
      error: null,
    };
  },
});
