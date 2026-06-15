/**
 * mo2_rollback — T3 restore from snapshotId.
 *
 * Plan returns manifest summary; apply runs SnapshotManager.restore() which
 * cp's backup files back over the source paths.
 */
import { z } from "zod";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { SnapshotManager } from "../snapshot.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), snapshot_id: z.string() }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
const handler = {
    toolName: "mo2_rollback",
    async buildPlan(args, ctx) {
        const snapshotId = args.snapshot_id;
        const sessionDir = join(ctx.config.snapshotRoot, ctx.sessionId);
        const dirs = await readdir(sessionDir).catch(() => []);
        for (const d of dirs) {
            const manifestPath = join(sessionDir, d, "manifest.json");
            try {
                const text = await readFile(manifestPath, "utf8");
                const manifest = JSON.parse(text);
                if (manifest.snapshotId === snapshotId) {
                    return {
                        diff: `Restore ${manifest.files.length} files from snapshot ${snapshotId} (tool=${manifest.tool}, ts=${manifest.ts})`,
                        affectedFiles: manifest.files.map((f) => f.source),
                        targets: manifest.files.map((f) => ({ path: f.source, kind: "text-file" })),
                    };
                }
            }
            catch {
                // skip malformed
            }
        }
        throw new Error(`snapshot_not_found: ${snapshotId}`);
    },
    async applyMutation(plan, ctx) {
        const sm = new SnapshotManager(ctx.config.snapshotRoot, ctx.sessionId);
        const result = await sm.restore(plan.args.snapshot_id);
        return result;
    },
};
registerTool({
    name: "mo2_rollback",
    tier: "T3",
    description: "Restore files from a snapshot_id created by an earlier T2/T3 apply. Plan returns manifest summary; apply does the cp.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
