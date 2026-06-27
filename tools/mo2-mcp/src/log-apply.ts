import type { BoundContext } from "./binding.js";

export async function logApplyEvent(
  toolName: string,
  summary: string,
  ctx: BoundContext,
  planId: string,
  profile: string,
): Promise<void> {
  if (!ctx.pipeClient) return;
  try {
    await ctx.pipeClient.call("system.log_apply", {
      tool: toolName,
      plan_id: planId,
      profile,
      summary,
    });
  } catch {
    // Best-effort only: audit logging must not fail a mutation.
  }
}
