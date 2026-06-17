/**
 * mo2_run_tool — T3 run a configured MO2 executable via VFS.
 *
 * Live path uses the broker's organizer.start_application and optional
 * organizer.wait_for_application calls. Offline fallback launches MO2's CLI
 * entrypoint with `run -e <title>` so the executable still runs through the
 * configured profile/VFS surface.
 */
import { spawn } from "node:child_process";
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { readMoIni } from "../mo-ini.js";
import { requireBoundContext } from "../binding.js";
// BUG-10 fix (2026-06-17): executable title + plan_id + lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        title: z.string().min(1),
        wait: z.boolean().default(false),
        profile: z.string().default("Default"),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);
function _configuredTitles(titles) {
    return titles.length > 0 ? titles.join(", ") : "<none>";
}
function _numberHandle(result) {
    const handle = result?.handle;
    if (typeof handle !== "number") {
        throw new Error("start_application_missing_handle");
    }
    return handle;
}
const handler = {
    toolName: "mo2_run_tool",
    async buildPlan(args, ctx) {
        const bound = requireBoundContext(ctx);
        const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
        const exe = ini.customExecutables.find((entry) => entry.title === args.title);
        if (!exe) {
            throw new Error(`executable_not_found: ${String(args.title)} (configured: ${_configuredTitles(ini.customExecutables.map((entry) => entry.title))})`);
        }
        return {
            diff: `Run ${exe.binary} ${exe.arguments ?? ""} via MO2 VFS (wait=${String(args.wait ?? false)})`,
            affectedFiles: [],
            targets: [],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const args = plan.args;
        const title = args.title;
        const wait = args.wait ?? false;
        const profile = args.profile ?? "Default";
        if (bound.pipeClient) {
            const started = await bound.pipeClient.call("organizer.start_application", {
                executable: title,
                args: [],
                cwd: "",
                profile,
                forcedCustomOverwrite: "",
                ignoreCustomOverwrite: false,
            });
            if (!started.ok)
                throw new Error(started.error?.message ?? "broker error");
            const handle = _numberHandle(started.result);
            if (wait) {
                const waited = await bound.pipeClient.call("organizer.wait_for_application", {
                    handle,
                    refresh: true,
                });
                if (!waited.ok)
                    throw new Error(waited.error?.message ?? "broker error");
                const waitResult = waited.result;
                return {
                    handle,
                    exit_code: typeof waitResult?.exit_code === "number" ? waitResult.exit_code : null,
                    success: waitResult?.success === true,
                };
            }
            return { handle, waiting: false };
        }
        const child = spawn(join(bound.config.mo2Root, "ModOrganizer.exe"), ["-p", profile, "run", "-e", title], { detached: !wait, stdio: "ignore" });
        if (!wait) {
            child.unref();
            return { pid: child.pid, waiting: false, source: "offline_cli" };
        }
        const exitCode = await new Promise((resolve) => {
            child.on("exit", (code) => resolve(code ?? -1));
        });
        return { exit_code: exitCode, source: "offline_cli" };
    },
};
registerTool({
    name: "mo2_run_tool",
    tier: "T3",
    description: "Run a configured customExecutable via MO2 VFS. Live: organizer.start_application. Offline: ModOrganizer run -e.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
