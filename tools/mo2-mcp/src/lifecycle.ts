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

export class Lifecycle {
  public state: LifecycleState = "not_started";
  public context: LifecycleContext = {};

  markStarting(): void {
    this.state = "starting";
    this.context.startedAt = Date.now();
  }

  markReady(ctx: Partial<LifecycleContext> = {}): void {
    this.state = "ready";
    this.context = { ...this.context, ...ctx, readyAt: Date.now() };
  }

  markFailed(reason: string): void {
    this.state = "failed";
    this.context.failureReason = reason;
  }

  requireReady():
    | { ok: true }
    | { ok: false; code: "not_ready"; state: LifecycleState; reason?: string } {
    if (this.state === "ready") return { ok: true };
    return {
      ok: false,
      code: "not_ready",
      state: this.state,
      reason: this.context.failureReason,
    };
  }
}
