import { loadConfig, type Config } from "./config.js";
import { readMoIni } from "./mo-ini.js";
import { detectMo2Running } from "./detection.js";
import { PipeClient } from "./pipe-client.js";
import { SidecarClient } from "./sidecar-client.js";
export type BindingState = "unbound" | "binding" | "bound" | "failed";
export interface BindingSnapshot {
    state: BindingState;
    mo2Root?: string;
    game?: string;
    profile?: string;
    pipeConnected?: boolean;
    sidecarReady?: boolean;
    error?: {
        code: string;
        message: string;
    };
}
export interface BoundContext {
    mo2Root: string;
    config: Config;
    pipeClient?: PipeClient;
    sidecar?: SidecarClient;
}
export interface BindingManagerOptions {
    loadConfig?: typeof loadConfig;
    readMoIni?: typeof readMoIni;
    detectMo2Running?: typeof detectMo2Running;
    createPipeClient?: () => PipeClient;
    createSidecarClient?: () => SidecarClient;
    log?: (message: string) => void;
    initialContext?: BoundContext;
    initialSnapshot?: BindingSnapshot;
}
export declare class BindingRequiredError extends Error {
    readonly code = "not_bound";
    readonly snapshot: BindingSnapshot;
    constructor(snapshot: BindingSnapshot);
}
/**
 * Production callers should carry `ctx.binding`; the legacy fallback only keeps
 * older direct-handler unit fixtures working while tests migrate to the v1.2
 * ToolContext shape. It is deliberately not part of ToolContext itself.
 */
export declare function requireBoundContext(ctx: {
    binding?: BindingManager;
} | unknown): BoundContext;
export declare function bindingSnapshot(ctx: {
    binding?: BindingManager;
} | unknown): BindingSnapshot;
export declare class BindingManager {
    private snapshot;
    private context?;
    private bindQueue;
    private readonly loadConfigFn;
    private readonly readMoIniFn;
    private readonly detectMo2RunningFn;
    private readonly createPipeClient;
    private readonly createSidecarClient;
    private readonly log;
    constructor(opts?: BindingManagerOptions);
    getSnapshot(): BindingSnapshot;
    bind(args: {
        mo2Root: string;
        profile?: string;
    }): Promise<BindingSnapshot>;
    /**
     * Awaits any in-flight bind() and returns the resulting snapshot. Used by
     * the central dispatcher so a tool call arriving during eager-bind window
     * (state="binding") transparently waits for the bind to settle before
     * resolving to `bound` or `failed`.
     */
    awaitSettled(): Promise<BindingSnapshot>;
    unbind(): Promise<void>;
    requireBound(): BoundContext;
    private bindNow;
    private tryStartSidecar;
    private tryConnectPipe;
    private cleanupCurrent;
}
