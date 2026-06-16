import { resolveProfileDir } from "../path-helpers.js";
export async function refreshOrganizer(ctx, opts = {}) {
    if (!ctx.pipeClient)
        return;
    const resp = await ctx.pipeClient.call("organizer.refresh", {
        save_changes: opts.saveChanges ?? false,
    });
    if (resp?.ok === false)
        throw new Error(resp.error?.message ?? "organizer.refresh failed");
}
export async function invalidateWorld(ctx, profiles = ["Default"]) {
    if (!ctx.sidecar)
        return;
    for (const profile of Array.from(new Set(profiles))) {
        await ctx.sidecar.call("world.invalidate", { profile_dir: resolveProfileDir(ctx, profile) });
    }
}
export async function refreshOrganizerAndInvalidateWorld(ctx, profiles = ["Default"], opts = {}) {
    // Broker mod mutations can return before MO2's model and the sidecar World
    // cache agree with the filesystem.  Keep the ordering explicit: first ask
    // MO2 to refresh its internal model, then evict sidecar cache entries that
    // were built from pre-mutation state.
    await refreshOrganizer(ctx, opts);
    await invalidateWorld(ctx, profiles);
}
