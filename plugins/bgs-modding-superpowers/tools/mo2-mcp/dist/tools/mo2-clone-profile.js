/**
 * mo2_clone_profile — T3 recursive profile copy while MO2 is closed.
 *
 * Filesystem-only clone. By default it skips volatile/heavy directories
 * (saves, logs, crashDumps) and .bak files.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { mkdir, readdir, copyFile } from "node:fs/promises";
import { extname, join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { detectMo2Running } from "../detection.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        source: z.string(),
        target: z.string(),
        include_saves: z.boolean().default(false),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
async function assertMo2Closed(mo2Root) {
    const det = await detectMo2Running({ mo2Root });
    if (det.processRunning)
        throw new Error("mo2_running: close MO2 before cloning profile");
}
async function copyDir(src, dst, skipDirs) {
    await mkdir(dst, { recursive: true });
    const entries = await readdir(src, { withFileTypes: true });
    for (const entry of entries) {
        const srcPath = join(src, entry.name);
        const dstPath = join(dst, entry.name);
        if (entry.isDirectory()) {
            if (skipDirs.has(entry.name))
                continue;
            await copyDir(srcPath, dstPath, skipDirs);
            continue;
        }
        if (extname(entry.name).toLowerCase() === ".bak")
            continue;
        await copyFile(srcPath, dstPath);
    }
}
const handler = {
    toolName: "mo2_clone_profile",
    async buildPlan(args, ctx) {
        await assertMo2Closed(ctx.config.mo2Root);
        const source = args.source;
        const target = args.target;
        const profilesRoot = join(ctx.config.mo2Root, "profiles");
        const srcDir = join(profilesRoot, source);
        const dstDir = join(profilesRoot, target);
        if (!existsSync(srcDir))
            throw new Error("source_profile_not_found");
        if (existsSync(dstDir))
            throw new Error("target_profile_exists");
        return {
            diff: `Clone profile ${source} → ${target} (include_saves=${String(args.include_saves ?? false)})`,
            affectedFiles: [dstDir],
            targets: [],
        };
    },
    async applyMutation(plan, ctx) {
        const source = plan.args.source;
        const target = plan.args.target;
        const includeSaves = plan.args.include_saves ?? false;
        const profilesRoot = join(ctx.config.mo2Root, "profiles");
        const srcDir = join(profilesRoot, source);
        const dstDir = join(profilesRoot, target);
        const skipDirs = new Set(["logs", "crashDumps"]);
        if (!includeSaves)
            skipDirs.add("saves");
        await copyDir(srcDir, dstDir, skipDirs);
        return { cloned_from: source, to: target, dst_path: dstDir };
    },
};
registerTool({
    name: "mo2_clone_profile",
    tier: "T3",
    description: "Clone a profile (MO2 must be closed). Skips saves/logs/crashDumps by default. include_saves=true to copy saves too.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
