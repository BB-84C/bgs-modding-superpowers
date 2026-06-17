/**
 * mo2_rollback — T3 restore from snapshotId.
 *
 * Plan returns manifest summary; apply runs SnapshotManager.restore() which
 * cp's backup files back over the source paths.
 *
 * Uses ctx.snapshots (the SnapshotManager constructed at server startup) for
 * both the manifest lookup and the actual restore — that instance owns the
 * canonical snapshotRoot (currently tmpdir/mo2-mcp-runtime/snapshots), which
 * is independent of bound.config.snapshotRoot after the v1.2-pre lazy-bind
 * refactor (server starts before any mo2Root is known).
 */
import { z } from "zod";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";
// BUG-10 fix (2026-06-17): snapshot_id + plan_id + lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), snapshot_id: z.string().min(1) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);
const handler = {
    toolName: "mo2_rollback",
    async buildPlan(args, ctx) {
        requireBoundContext(ctx); // enforce bound state, but use ctx.snapshots not config.snapshotRoot
        const snapshotId = args.snapshot_id;
        const manifest = await ctx.snapshots.findManifest(snapshotId);
        if (!manifest)
            throw new Error(`snapshot_not_found: ${snapshotId}`);
        return {
            diff: `Restore ${manifest.files.length} files from snapshot ${snapshotId} (tool=${manifest.tool}, ts=${manifest.ts})`,
            affectedFiles: manifest.files.map((f) => f.source),
            targets: manifest.files.map((f) => ({ path: f.source, kind: "text-file" })),
        };
    },
    async applyMutation(plan, ctx) {
        requireBoundContext(ctx);
        const result = await ctx.snapshots.restore(plan.args.snapshot_id);
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
// referenced for compat warning silence
void bindingSnapshot;
