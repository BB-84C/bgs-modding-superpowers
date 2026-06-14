/**
 * mo2_audit_query — T1 query MCP's own audit log.
 *
 * Reads JSONL files under auditRoot, filters by date range / tool /
 * decision / plan_id. Bounded by max_results.
 */
import { z } from "zod";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";

const inputSchema = z.object({
  date_from: z.string().optional(), // YYYY-MM-DD
  date_to: z.string().optional(),
  tool: z.string().optional(),
  decision: z
    .enum(["ok", "refused", "plan_generated", "applied", "lease_violation", "rolled_back"])
    .optional(),
  plan_id: z.string().optional(),
  max_results: z.number().int().min(1).max(5000).default(500),
});

registerTool({
  name: "mo2_audit_query",
  tier: "T1",
  description:
    "Query MCP audit log. Filters: date_from/date_to (YYYY-MM-DD), tool, decision, plan_id. Bounded by max_results (default 500). Returns records array + count + truncated.",
  inputSchema,
  handler: async (args, ctx) => {
    const maxResults = (args.max_results as number) ?? 500;
    const files = await readdir(ctx.config.auditRoot).catch(() => [] as string[]);
    const matched: Array<Record<string, unknown>> = [];
    let truncated = false;

    for (const f of files) {
      if (!f.endsWith(".jsonl")) continue;
      const dateMatch = f.match(/(\d{4}-\d{2}-\d{2})\.jsonl$/);
      if (!dateMatch) continue;
      const fileDate = dateMatch[1];
      if (args.date_from && fileDate < (args.date_from as string)) continue;
      if (args.date_to && fileDate > (args.date_to as string)) continue;

      let text: string;
      try {
        text = await readFile(join(ctx.config.auditRoot, f), "utf8");
      } catch {
        continue;
      }

      for (const line of text.split("\n")) {
        if (!line.trim()) continue;
        let rec: Record<string, unknown>;
        try {
          rec = JSON.parse(line);
        } catch {
          continue;
        }
        if (args.tool && rec.tool !== args.tool) continue;
        if (args.decision && rec.decision !== args.decision) continue;
        if (args.plan_id && rec.planId !== args.plan_id) continue;
        matched.push(rec);
        if (matched.length >= maxResults) {
          truncated = true;
          break;
        }
      }
      if (truncated) break;
    }

    return {
      ok: true,
      result: { records: matched, count: matched.length, truncated },
      error: null,
    };
  },
});
