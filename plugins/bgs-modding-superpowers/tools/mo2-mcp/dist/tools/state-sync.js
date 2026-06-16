import { resolveProfileDir } from "../path-helpers.js";
/**
 * Sidecar World cache invalidation after mod-mutation operations.
 *
 * Previously this module also exposed `refreshOrganizer` / `refreshOrganizerAndInvalidateWorld`
 * which invoked broker `organizer.refresh`.  That call was reverted because it caused
 * MO2 to attempt mod-list rewrites against a transiently inconsistent in-memory model
 * (user observed "failed to write mod list: invalid mod index: N" dialogs and modlist
 * corruption).  MO2's own internal save/refresh cycle is sufficient; we only need to
 * tell the sidecar to drop its World cache so subsequent assets reads pick up the
 * post-mutation filesystem state.
 */
export async function invalidateWorld(ctx, profiles = ["Default"]) {
    if (!ctx.sidecar)
        return;
    for (const profile of Array.from(new Set(profiles))) {
        await ctx.sidecar.call("world.invalidate", { profile_dir: resolveProfileDir(ctx, profile) });
    }
}
