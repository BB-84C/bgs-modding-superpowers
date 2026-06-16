import type { ToolContext } from "../types.js";
import { resolveProfileDir } from "../path-helpers.js";

interface BrokerEnvelope {
  ok?: boolean;
  error?: { message?: string } | null;
}

export async function refreshOrganizer(
  ctx: ToolContext,
  opts: { saveChanges?: boolean } = {},
): Promise<void> {
  if (!ctx.pipeClient) return;
  const resp = await ctx.pipeClient.call("organizer.refresh", {
    save_changes: opts.saveChanges ?? false,
  }) as BrokerEnvelope;
  if (resp?.ok === false) throw new Error(resp.error?.message ?? "organizer.refresh failed");
}

export async function invalidateWorld(
  ctx: ToolContext,
  profiles: string[] = ["Default"],
): Promise<void> {
  if (!ctx.sidecar) return;
  for (const profile of Array.from(new Set(profiles))) {
    await ctx.sidecar.call("world.invalidate", { profile_dir: resolveProfileDir(ctx, profile) });
  }
}

export async function refreshOrganizerAndInvalidateWorld(
  ctx: ToolContext,
  profiles: string[] = ["Default"],
  opts: { saveChanges?: boolean } = {},
): Promise<void> {
  // Broker mod mutations can return before MO2's model and the sidecar World
  // cache agree with the filesystem.  Keep the ordering explicit: first ask
  // MO2 to refresh its internal model, then evict sidecar cache entries that
  // were built from pre-mutation state.
  await refreshOrganizer(ctx, opts);
  await invalidateWorld(ctx, profiles);
}
