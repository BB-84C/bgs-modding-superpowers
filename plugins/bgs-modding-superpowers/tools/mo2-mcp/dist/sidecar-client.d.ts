export type SidecarGame = "FALLOUT4" | "SKYRIM_SE" | "SKYRIM_LE" | "STARFIELD" | "OBLIVION" | "FALLOUT_NV";
export interface SidecarStartOptions {
    pythonPath?: string;
    modsRoot: string;
    profileDir?: string;
    game: SidecarGame;
}
export declare class SidecarClient {
    private proc?;
    private buffer;
    private pending;
    private nextId;
    private ready;
    private lastStartOptions?;
    private restartAttempts;
    private readonly maxRestarts;
    private stopping;
    private permanentFailed;
    private lastExitReason?;
    start(opts: SidecarStartOptions): Promise<void>;
    private launch;
    private onExit;
    private onData;
    call(method: string, params?: unknown, timeoutMs?: number): Promise<unknown>;
    isReady(): boolean;
    stop(): Promise<void>;
}
