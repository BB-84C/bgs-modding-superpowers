/**
 * Lifecycle state machine for the MO2 MCP server.
 * Ported from xedit-mcp pattern: states transition not_started -> starting -> ready,
 * or any -> failed. Domain tools require ready state.
 */
export type LifecycleState = "not_started" | "starting" | "ready" | "failed";
export interface LifecycleContext {
    sidecarPid?: number;
    brokerPipeName?: string;
    failureReason?: string;
    startedAt?: number;
    readyAt?: number;
}
export declare class Lifecycle {
    state: LifecycleState;
    context: LifecycleContext;
    markStarting(): void;
    markReady(ctx?: Partial<LifecycleContext>): void;
    markFailed(reason: string): void;
    requireReady(): {
        ok: true;
    } | {
        ok: false;
        code: "not_ready";
        state: LifecycleState;
        reason?: string;
    };
}
