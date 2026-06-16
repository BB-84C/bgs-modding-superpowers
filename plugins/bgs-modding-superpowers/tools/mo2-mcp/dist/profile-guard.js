import { requireBoundContext } from "./binding.js";
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
        throw new Error(`cross_profile_live_mutation_blocked: requested='${requestedProfile}', active='${result.name}'. ` +
            "Use mo2_switch_profile to switch first, or stop MO2 to use offline mutation.");
    }
}
