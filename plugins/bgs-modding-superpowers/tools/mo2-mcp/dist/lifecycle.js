export class Lifecycle {
    state = "not_started";
    context = {};
    markStarting() {
        this.state = "starting";
        this.context.startedAt = Date.now();
    }
    markReady(ctx = {}) {
        this.state = "ready";
        this.context = { ...this.context, ...ctx, readyAt: Date.now() };
    }
    markFailed(reason) {
        this.state = "failed";
        this.context.failureReason = reason;
    }
    requireReady() {
        if (this.state === "ready")
            return { ok: true };
        return {
            ok: false,
            code: "not_ready",
            state: this.state,
            reason: this.context.failureReason,
        };
    }
}
