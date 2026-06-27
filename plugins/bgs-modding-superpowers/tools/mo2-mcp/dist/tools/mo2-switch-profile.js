/**
 * mo2_switch_profile — T3 cold-restart MO2 under a different profile.
 *
 * Sequence: broker shutdown ACK → wait for old PID to disappear → launch
 * ModOrganizer.exe -p <profile> → wait for fresh endpoint.json + status.json
 * with matching PID → reconnect PipeClient → invalidate sidecar world cache.
 */
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { z } from "zod";
import { detectMo2Running } from "../detection.js";
import { PipeClient } from "../pipe-client.js";
import { routeToPlanApply } from "../plan-apply.js";
import { resolveProfileDir } from "../path-helpers.js";
import { registerTool } from "../tool-registry.js";
import { requireBoundContext } from "../binding.js";
import { logApplyEvent } from "../log-apply.js";
// BUG-10 fix (2026-06-17): new_profile + plan_id + lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), new_profile: z.string().min(1) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);
function _delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
async function _waitForMo2Gone(mo2Root) {
    for (let i = 0; i < 30; i++) {
        const det = await detectMo2Running({ mo2Root });
        if (!det.processRunning)
            return;
        await _delay(1000);
    }
    throw new Error("mo2_shutdown_timeout_30s");
}
async function _waitForFreshEndpoint(mo2Root) {
    const runtimeDir = join(mo2Root, "plugins", "Mo2AgentControl", "bootstrap", "runtime");
    const endpointPath = join(runtimeDir, "endpoint.json");
    const statusPath = join(runtimeDir, "status.json");
    for (let i = 0; i < 60; i++) {
        try {
            const info = JSON.parse(await readFile(endpointPath, "utf8"));
            const status = JSON.parse(await readFile(statusPath, "utf8"));
            const det = await detectMo2Running({ mo2Root });
            if (typeof info.endpoint === "string" &&
                status.state === "ok" &&
                typeof status.mo2Pid === "number" &&
                det.processRunning &&
                det.pid === status.mo2Pid) {
                return info.endpoint;
            }
        }
        catch {
            // Not ready yet; keep polling until timeout.
        }
        await _delay(2000);
    }
    throw new Error("mo2_ready_timeout_120s");
}
async function _shutdownCurrentPipe(ctx) {
    const bound = requireBoundContext(ctx);
    if (!bound.pipeClient)
        return;
    const resp = await bound.pipeClient.call("system.shutdown", {}, 10000);
    if (!resp.ok)
        throw new Error(`shutdown_failed: ${resp.error?.message ?? "broker error"}`);
    bound.pipeClient.close();
}
const handler = {
    toolName: "mo2_switch_profile",
    async buildPlan(args, ctx) {
        const bound = requireBoundContext(ctx);
        const newProfile = args.new_profile;
        const newProfileDir = resolveProfileDir(ctx, newProfile);
        if (!existsSync(newProfileDir))
            throw new Error(`profile_not_found: ${newProfile}`);
        if (!bound.config.allowedProfiles.includes(newProfile)) {
            throw new Error(`profile_not_allowed: ${newProfile}`);
        }
        return {
            diff: `Cold-restart MO2 with -p ${newProfile}: shutdown → wait_dead → launch → wait_ready → sidecar_invalidate`,
            affectedFiles: [],
            targets: [],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const oldProfile = bound.config.allowedProfiles[0] ?? "";
        const newProfile = plan.args.new_profile;
        await _shutdownCurrentPipe(ctx);
        await _waitForMo2Gone(bound.config.mo2Root);
        const child = spawn(join(bound.config.mo2Root, "ModOrganizer.exe"), ["-p", newProfile], { detached: true, stdio: "ignore" });
        child.unref();
        const newPipe = await _waitForFreshEndpoint(bound.config.mo2Root);
        const newClient = new PipeClient();
        await newClient.discoverAndConnect(bound.config.mo2Root);
        bound.pipeClient = newClient;
        if (bound.sidecar) {
            await bound.sidecar.call("world.invalidate", {
                profile_dir: resolveProfileDir(ctx, newProfile),
            });
        }
        await logApplyEvent(handler.toolName, `switched profile "${oldProfile}" → "${newProfile}"`, bound, plan.planId, newProfile);
        return { new_profile: newProfile, new_pipe: newPipe };
    },
};
registerTool({
    name: "mo2_switch_profile",
    tier: "T3",
    description: "Cold-restart MO2 with a different profile. Shutdown → wait_dead → relaunch → wait_ready → sidecar_invalidate. Refuses profiles outside allowedProfiles.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
