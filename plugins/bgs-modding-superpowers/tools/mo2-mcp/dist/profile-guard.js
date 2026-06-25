import { join } from "node:path";
import { requireBoundContext } from "./binding.js";
import { readMoIni } from "./mo-ini.js";
const METHOD_NOT_FOUND_CODE = "method_not_found";
const UNSUPPORTED_METHOD_PREFIX = "Unsupported method";
/**
 * Resolve the live active profile, preferring broker `profile.active` and
 * falling back to `ModOrganizer.ini [General] selected_profile` when the
 * deployed broker lacks the handler.
 *
 * BUG-23 (issue #12) fix (2026-06-25): the MCP wire layer (tools/mo2-mcp) is
 * version-synced through the materialized plugin tree, but the Python broker
 * lives at <MO2_Root>/plugins/mo2_agent_control.py and is per-instance
 * deployed by install-mo2-control-plane.ps1. A stale broker — one that
 * predates the addition of `profile.active` and `mods.meta_write` handlers —
 * silently breaks every T3 mutating tool because assertActiveProfile bombs on
 * `Unsupported method: profile.active` (collapsed to `internal_error` by
 * dispatch.ts). The ini fallback uses the same decodeIniValue path that
 * mo2_modlist already relies on, so Chinese / non-ASCII profile names work
 * correctly. We emit a one-time stderr warning per session so the user knows
 * a redeploy is recommended for the more accurate broker path (which reflects
 * mid-session profile switches before MO2 flushes selected_profile to disk).
 */
async function resolveActiveProfile(ctx) {
    const bound = requireBoundContext(ctx);
    const pipeClient = bound.pipeClient;
    if (pipeClient) {
        try {
            const response = await pipeClient.call("profile.active", {});
            if (response.ok) {
                const result = response.result;
                if (typeof result?.name === "string" && result.name.length > 0) {
                    return result.name;
                }
                // Broker returned ok but no name — treat as unavailable, fall through.
            }
            else if (response.error?.code !== METHOD_NOT_FOUND_CODE) {
                // Real broker error, not a stale-broker symptom; surface it.
                throw new Error(response.error?.message ?? "profile.active broker error");
            }
            else {
                warnStaleBroker("profile.active");
            }
        }
        catch (e) {
            const message = e instanceof Error ? e.message : String(e);
            if (!message.startsWith(UNSUPPORTED_METHOD_PREFIX))
                throw e;
            warnStaleBroker("profile.active");
        }
    }
    // INI fallback. Works without MO2 running; matches mo2_modlist semantics.
    try {
        const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
        return ini.general.selectedProfile ?? null;
    }
    catch {
        return null;
    }
}
const STALE_BROKER_WARNED = new Set();
function warnStaleBroker(method) {
    if (STALE_BROKER_WARNED.has(method))
        return;
    STALE_BROKER_WARNED.add(method);
    process.stderr.write(`[mo2-mcp] broker lacks '${method}' handler; falling back. ` +
        "Consider redeploying via tools/mo2-control-plane/install-mo2-control-plane.ps1 " +
        "and restarting MO2.\n");
}
/** @internal test-only reset for the dedup'd warning state. */
export function _resetStaleBrokerWarnedForTests() {
    STALE_BROKER_WARNED.clear();
}
/**
 * Structured error thrown when assertActiveProfile detects MO2 is alive on a
 * different profile than the requested mutation target.
 *
 * BUG-21 fix (2026-06-17): assertActiveProfile previously threw a plain
 * `Error("cross_profile_live_mutation_blocked: ...")`. dispatch.ts caught
 * the generic Error and wrapped it as `code: "internal_error"`, dropping the
 * stable code that agent decision logic needs. Same shape as
 * BrokerEnrichedError + BindingRequiredError: typed subclass with `code` and
 * `details`, plus a dispatch.ts catch branch that surfaces the structured
 * envelope. The message text preserves the legacy
 * `cross_profile_live_mutation_blocked: requested='X', active='Y'` prefix so
 * all existing `.rejects.toThrow(/cross_profile_live_mutation_blocked/)`
 * tests keep matching.
 */
export class CrossProfileMutationError extends Error {
    code = "cross_profile_live_mutation_blocked";
    details;
    constructor(args) {
        super(`cross_profile_live_mutation_blocked: requested='${args.requested}', active='${args.active}'. ` +
            "Use mo2_switch_profile to switch first, or stop MO2 to use offline mutation.");
        this.name = "CrossProfileMutationError";
        this.details = {
            requested: args.requested,
            active: args.active,
            hint: "Use mo2_switch_profile to switch first, or stop MO2 to use offline mutation.",
        };
    }
}
export async function assertActiveProfile(ctx, requestedProfile) {
    const bound = requireBoundContext(ctx);
    // No live pipe = MO2 offline = mutations land via offline INI rewrites. The
    // cross-profile guard exists to stop live-MO2 mutations against a different
    // in-memory profile; without a live pipe there is nothing to gate.
    if (!bound.pipeClient)
        return;
    const active = await resolveActiveProfile(ctx);
    if (active === null) {
        throw new Error("active_profile_unavailable: profile.active returned no profile name");
    }
    if (active !== requestedProfile) {
        throw new CrossProfileMutationError({
            requested: requestedProfile,
            active,
        });
    }
}
