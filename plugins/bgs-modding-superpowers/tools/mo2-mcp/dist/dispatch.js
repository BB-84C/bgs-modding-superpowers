/** Central MCP tool-call dispatch: lookup -> schema validation -> rules -> handler. */
import { getTool } from "./tool-registry.js";
import { hashArgs } from "./audit.js";
import { runRules, hasBlocking } from "./pipeline/rules.js";
import { BindingRequiredError, bindingSnapshot } from "./binding.js";
import { BrokerEnrichedError } from "./broker-error.js";
import { CrossProfileMutationError } from "./profile-guard.js";
function jsonText(value) {
    return { type: "text", text: JSON.stringify(value) };
}
function isBindingExemptTool(toolName) {
    return toolName === "mo2_session" || toolName === "mo2_status" || toolName === "mo2_machine_contract";
}
function notBoundEnvelope(ctx) {
    return {
        ok: false,
        error: {
            code: "not_bound",
            message: "MO2 MCP is not bound to an MO2 root.",
            snapshot: bindingSnapshot(ctx),
            hint: "call mo2_session({ mo2Root }) to bind",
        },
    };
}
export async function dispatchToolCall({ toolName, rawArgs, ctx, rules, }) {
    const t0 = Date.now();
    const tool = getTool(toolName);
    if (!tool) {
        await ctx.audit.log({
            ts: new Date().toISOString(),
            sessionId: ctx.sessionId,
            tool: toolName,
            argsHash: hashArgs(rawArgs),
            decision: "refused",
            durationMs: Date.now() - t0,
            error: { code: "tool_not_found", message: toolName },
        });
        return {
            content: [jsonText({ ok: false, error: { code: "tool_not_found" } })],
        };
    }
    const argsForParse = rawArgs ?? {};
    const parseResult = tool.inputSchema.safeParse(argsForParse);
    if (!parseResult.success) {
        const flat = parseResult.error.flatten();
        await ctx.audit.log({
            ts: new Date().toISOString(),
            sessionId: ctx.sessionId,
            tool: tool.name,
            argsHash: hashArgs(argsForParse),
            decision: "refused",
            durationMs: Date.now() - t0,
            error: {
                code: "invalid_arguments",
                message: "Tool arguments failed schema validation",
            },
            details: flat,
        });
        return {
            content: [
                jsonText({
                    ok: false,
                    error: {
                        code: "invalid_arguments",
                        message: "Tool arguments failed schema validation",
                        field_errors: flat.fieldErrors,
                        form_errors: flat.formErrors,
                    },
                }),
            ],
            isError: true,
        };
    }
    const validatedArgs = parseResult.data;
    // If a bind is currently in-flight (e.g. eager auto-bind triggered by env at
    // startup), wait for it to settle before dispatching — clients shouldn't have
    // to poll mo2_session just because their first tool call raced the bind. We
    // apply this to ALL tools including binding-exempt ones (mo2_status,
    // mo2_machine_contract, mo2_session): mo2_status is meant to return the
    // bound view when a bind is imminent, and mo2_session's own bind/unbind
    // operations are serialized by BindingManager.bindQueue so chaining one
    // after an in-flight bind is safe (it just appends to the queue).
    if (ctx.binding && bindingSnapshot(ctx).state === "binding") {
        await ctx.binding.awaitSettled();
    }
    if (!isBindingExemptTool(tool.name) && bindingSnapshot(ctx).state !== "bound") {
        const env = notBoundEnvelope(ctx);
        await ctx.audit.log({
            ts: new Date().toISOString(),
            sessionId: ctx.sessionId,
            tool: tool.name,
            argsHash: hashArgs(argsForParse),
            decision: "refused",
            durationMs: Date.now() - t0,
            error: { code: env.error.code, message: env.error.message },
            details: { snapshot: env.error.snapshot },
        });
        return { content: [jsonText(env)] };
    }
    const findings = await runRules(rules, tool.name, ctx, validatedArgs);
    if (hasBlocking(findings)) {
        const blocking = findings.find((f) => f.decision === "block");
        await ctx.audit.log({
            ts: new Date().toISOString(),
            sessionId: ctx.sessionId,
            tool: tool.name,
            argsHash: hashArgs(argsForParse),
            decision: "refused",
            ruleFindings: findings,
            durationMs: Date.now() - t0,
            error: { code: blocking.code, message: blocking.message },
        });
        return {
            content: [jsonText({ ok: false, error: blocking })],
        };
    }
    try {
        const result = await tool.handler(validatedArgs, ctx);
        const mode = validatedArgs.mode;
        const resultObj = result;
        await ctx.audit.log({
            ts: new Date().toISOString(),
            sessionId: ctx.sessionId,
            tool: tool.name,
            mode,
            argsHash: hashArgs(argsForParse),
            decision: resultObj?.ok === false
                ? "refused"
                : mode === "plan"
                    ? "plan_generated"
                    : mode === "apply"
                        ? "applied"
                        : "ok",
            durationMs: Date.now() - t0,
            plan_id: resultObj?.result?.plan_id,
            snapshotId: resultObj?.result?.snapshot_id,
        });
        return { content: [jsonText(result)] };
    }
    catch (e) {
        if (e instanceof BindingRequiredError) {
            const env = notBoundEnvelope(ctx);
            await ctx.audit.log({
                ts: new Date().toISOString(),
                sessionId: ctx.sessionId,
                tool: tool.name,
                argsHash: hashArgs(argsForParse),
                decision: "refused",
                durationMs: Date.now() - t0,
                error: { code: env.error.code, message: env.error.message },
                details: { snapshot: e.snapshot },
            });
            return { content: [jsonText(env)] };
        }
        if (e instanceof BrokerEnrichedError) {
            // ENRICHMENT-DESIGN.md Lane B: broker failures arrive carrying the L1
            // process responsiveness probe + L2 mo2.log tail in `details`. Surface
            // those to the agent and audit them with the structured code so
            // BUG-16-class hangs become diagnosable instead of opaque timeouts.
            await ctx.audit.log({
                ts: new Date().toISOString(),
                sessionId: ctx.sessionId,
                tool: tool.name,
                argsHash: hashArgs(argsForParse),
                decision: "refused",
                durationMs: Date.now() - t0,
                error: { code: e.code, message: e.message },
                details: e.details,
            });
            return {
                content: [
                    jsonText({
                        ok: false,
                        error: { code: e.code, message: e.message, details: e.details },
                    }),
                ],
            };
        }
        if (e instanceof CrossProfileMutationError) {
            // BUG-21 fix (2026-06-17): cross-profile guard surfaces a structured
            // envelope with the stable code `cross_profile_live_mutation_blocked`
            // and the requested/active profile pair in `details`. Without this
            // branch the generic Error fallback below collapses the code to
            // `internal_error`, which is correct behavior but unusable for agent
            // decision logic.
            await ctx.audit.log({
                ts: new Date().toISOString(),
                sessionId: ctx.sessionId,
                tool: tool.name,
                argsHash: hashArgs(argsForParse),
                decision: "refused",
                durationMs: Date.now() - t0,
                error: { code: e.code, message: e.message },
                details: e.details,
            });
            return {
                content: [
                    jsonText({
                        ok: false,
                        error: { code: e.code, message: e.message, details: e.details },
                    }),
                ],
            };
        }
        const msg = e instanceof Error ? e.message : String(e);
        await ctx.audit.log({
            ts: new Date().toISOString(),
            sessionId: ctx.sessionId,
            tool: tool.name,
            argsHash: hashArgs(argsForParse),
            decision: "refused",
            durationMs: Date.now() - t0,
            error: { code: "internal_error", message: msg },
        });
        return {
            content: [
                jsonText({
                    ok: false,
                    error: { code: "internal_error", message: msg },
                }),
            ],
        };
    }
}
