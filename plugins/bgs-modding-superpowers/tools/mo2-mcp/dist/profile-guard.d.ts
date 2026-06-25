import type { ToolContext } from "./types.js";
/** @internal test-only reset for the dedup'd warning state. */
export declare function _resetStaleBrokerWarnedForTests(): void;
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
export declare class CrossProfileMutationError extends Error {
    readonly code = "cross_profile_live_mutation_blocked";
    readonly details: {
        requested: string;
        active: string;
        hint: string;
    };
    constructor(args: {
        requested: string;
        active: string;
    });
}
export declare function assertActiveProfile(ctx: ToolContext, requestedProfile: string): Promise<void>;
