export async function logApplyEvent(toolName, summary, ctx, planId, profile) {
    if (!ctx.pipeClient)
        return;
    try {
        await ctx.pipeClient.call("system.log_apply", {
            tool: toolName,
            plan_id: planId,
            profile,
            summary,
        });
    }
    catch {
        // Best-effort only: audit logging must not fail a mutation.
    }
}
