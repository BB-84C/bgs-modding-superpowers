import { join } from "node:path";
import { loadConfig } from "./config.js";
import { readMoIni } from "./mo-ini.js";
import { detectMo2Running } from "./detection.js";
import { PipeClient } from "./pipe-client.js";
import { SidecarClient } from "./sidecar-client.js";
export class BindingRequiredError extends Error {
    code = "not_bound";
    snapshot;
    constructor(snapshot) {
        super("MO2 MCP is not bound; call mo2_session({ mo2Root }) to bind before using this tool.");
        this.name = "BindingRequiredError";
        this.snapshot = snapshot;
    }
}
/**
 * Production callers should carry `ctx.binding`; the legacy fallback only keeps
 * older direct-handler unit fixtures working while tests migrate to the v1.2
 * ToolContext shape. It is deliberately not part of ToolContext itself.
 */
export function requireBoundContext(ctx) {
    const maybe = ctx;
    if (maybe.binding)
        return maybe.binding.requireBound();
    if (maybe.config) {
        // Legacy fixture compat: tools occasionally mutate bound.pipeClient or
        // bound.sidecar at runtime (e.g. mo2_switch_profile reconnects after
        // cold-restart). Expose those as getter/setter pass-throughs so the
        // mutation is visible on the underlying ctx — which is what pre-refactor
        // unit tests assert on.
        const bound = {
            mo2Root: maybe.config.mo2Root,
            config: maybe.config,
        };
        Object.defineProperty(bound, "pipeClient", {
            get: () => maybe.pipeClient,
            set: (value) => {
                maybe.pipeClient = value;
            },
            enumerable: true,
            configurable: true,
        });
        Object.defineProperty(bound, "sidecar", {
            get: () => maybe.sidecar,
            set: (value) => {
                maybe.sidecar = value;
            },
            enumerable: true,
            configurable: true,
        });
        return bound;
    }
    throw new BindingRequiredError({ state: "unbound" });
}
export function bindingSnapshot(ctx) {
    const maybe = ctx;
    if (maybe.binding)
        return maybe.binding.getSnapshot();
    if (maybe.config) {
        return {
            state: "bound",
            mo2Root: maybe.config.mo2Root,
            profile: maybe.config.allowedProfiles[0],
            pipeConnected: !!maybe.pipeClient,
            sidecarReady: !!maybe.sidecar,
        };
    }
    return { state: "unbound" };
}
const GAME_MAP = {
    fallout4: "FALLOUT4",
    skyrimSE: "SKYRIM_SE",
    skyrimLE: "SKYRIM_LE",
    starfield: "STARFIELD",
    oblivion: "OBLIVION",
    falloutNV: "FALLOUT_NV",
};
export class BindingManager {
    snapshot;
    context;
    bindQueue = Promise.resolve({ state: "unbound" });
    loadConfigFn;
    readMoIniFn;
    detectMo2RunningFn;
    createPipeClient;
    createSidecarClient;
    log;
    constructor(opts = {}) {
        this.loadConfigFn = opts.loadConfig ?? loadConfig;
        this.readMoIniFn = opts.readMoIni ?? readMoIni;
        this.detectMo2RunningFn = opts.detectMo2Running ?? detectMo2Running;
        this.createPipeClient = opts.createPipeClient ?? (() => new PipeClient());
        this.createSidecarClient = opts.createSidecarClient ?? (() => new SidecarClient());
        this.log = opts.log ?? ((message) => process.stderr.write(message));
        this.context = opts.initialContext;
        this.snapshot = opts.initialSnapshot ?? snapshotForInitialContext(opts.initialContext);
    }
    getSnapshot() {
        return cloneSnapshot(this.snapshot);
    }
    bind(args) {
        const run = this.bindQueue.then(() => this.bindNow(args));
        this.bindQueue = run.catch(() => this.getSnapshot());
        return run;
    }
    /**
     * Awaits any in-flight bind() and returns the resulting snapshot. Used by
     * the central dispatcher so a tool call arriving during eager-bind window
     * (state="binding") transparently waits for the bind to settle before
     * resolving to `bound` or `failed`.
     */
    async awaitSettled() {
        await this.bindQueue.catch(() => undefined);
        return this.getSnapshot();
    }
    async unbind() {
        await this.bindQueue.catch(() => undefined);
        await this.cleanupCurrent();
        this.context = undefined;
        this.snapshot = { state: "unbound" };
    }
    requireBound() {
        if (this.snapshot.state !== "bound" || !this.context) {
            throw new BindingRequiredError(this.getSnapshot());
        }
        return this.context;
    }
    async bindNow(args) {
        await this.cleanupCurrent();
        this.context = undefined;
        this.snapshot = {
            state: "binding",
            mo2Root: args.mo2Root,
            profile: args.profile,
            pipeConnected: false,
            sidecarReady: false,
        };
        let sidecar;
        let pipe;
        try {
            const loadedConfig = await this.loadConfigFn({ mo2Root: args.mo2Root });
            const effectiveProfile = args.profile ?? loadedConfig.allowedProfiles[0] ?? "Default";
            const config = promoteBoundProfile(loadedConfig, effectiveProfile);
            const ini = await this.readMoIniFn(join(args.mo2Root, "ModOrganizer.ini"));
            const profileDir = join(args.mo2Root, "profiles", effectiveProfile);
            const game = ini.general.game ?? "fallout4";
            sidecar = await this.tryStartSidecar(args.mo2Root, ini, profileDir, game);
            const detection = await this.detectMo2RunningFn({ mo2Root: args.mo2Root, profileDir });
            pipe = await this.tryConnectPipe(args.mo2Root, detection);
            this.context = {
                mo2Root: args.mo2Root,
                config,
                pipeClient: pipe?.isConnected() ? pipe : undefined,
                sidecar: sidecar?.isReady() ? sidecar : undefined,
            };
            this.snapshot = {
                state: "bound",
                mo2Root: args.mo2Root,
                game,
                profile: effectiveProfile,
                pipeConnected: !!this.context.pipeClient,
                sidecarReady: !!this.context.sidecar,
            };
            return this.getSnapshot();
        }
        catch (error) {
            await cleanupPartial(sidecar, pipe);
            this.context = undefined;
            this.snapshot = {
                state: "failed",
                mo2Root: args.mo2Root,
                profile: args.profile,
                pipeConnected: false,
                sidecarReady: false,
                error: { code: "bind_failed", message: errorMessage(error) },
            };
            return this.getSnapshot();
        }
    }
    async tryStartSidecar(mo2Root, ini, profileDir, game) {
        const sidecar = this.createSidecarClient();
        try {
            await sidecar.start({
                modsRoot: ini.settings.modDirectory ?? join(mo2Root, "mods"),
                profileDir,
                game: GAME_MAP[game] ?? "FALLOUT4",
            });
            return sidecar;
        }
        catch (error) {
            this.log(`[mo2-mcp] sidecar failed to start: ${errorMessage(error)}\n`);
            await sidecar.stop().catch(() => undefined);
            return undefined;
        }
    }
    async tryConnectPipe(mo2Root, detection) {
        if (!detection.online)
            return undefined;
        const pipe = this.createPipeClient();
        try {
            await pipe.discoverAndConnect(mo2Root, 5000, { expectedPid: detection.pid ?? undefined });
            return pipe.isConnected() ? pipe : undefined;
        }
        catch (error) {
            this.log(`[mo2-mcp] broker pipe unavailable: ${errorMessage(error)}\n`);
            pipe.close();
            return undefined;
        }
    }
    async cleanupCurrent() {
        const current = this.context;
        if (!current)
            return;
        await cleanupPartial(current.sidecar, current.pipeClient);
        this.context = undefined;
    }
}
function promoteBoundProfile(config, profile) {
    return {
        ...config,
        allowedProfiles: [profile, ...config.allowedProfiles.filter((candidate) => candidate !== profile)],
    };
}
async function cleanupPartial(sidecar, pipe) {
    if (sidecar)
        await sidecar.stop().catch(() => undefined);
    if (pipe)
        pipe.close();
}
function snapshotForInitialContext(context) {
    if (!context)
        return { state: "unbound" };
    return {
        state: "bound",
        mo2Root: context.mo2Root,
        profile: context.config.allowedProfiles[0],
        pipeConnected: !!context.pipeClient,
        sidecarReady: !!context.sidecar,
    };
}
function cloneSnapshot(snapshot) {
    return {
        ...snapshot,
        error: snapshot.error ? { ...snapshot.error } : undefined,
    };
}
function errorMessage(error) {
    return error instanceof Error ? error.message : String(error);
}
