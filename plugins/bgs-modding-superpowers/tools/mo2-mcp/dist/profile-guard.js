import { requireBoundContext } from "./binding.js";
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
    const pipeClient = requireBoundContext(ctx).pipeClient;
    if (!pipeClient)
        return;
    const response = await pipeClient.call("profile.active", {});
    if (!response.ok) {
        throw new Error(response.error?.message ?? "profile.active broker error");
    }
    const result = response.result;
    if (typeof result?.name !== "string") {
        throw new Error("active_profile_unavailable: profile.active returned no profile name");
    }
    if (result.name !== requestedProfile) {
        throw new CrossProfileMutationError({
            requested: requestedProfile,
            active: result.name,
        });
    }
}
