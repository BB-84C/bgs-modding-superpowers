/**
 * Python sidecar JSON-RPC client (spawn-once, multiplex by id).
 *
 * Spawns `python -m mo2_mcp_sidecar` as a long-lived subprocess.
 * Waits for `{"ready": true}` on stdout before resolving start().
 * All subsequent calls use a request id and pending map (sidecar handles
 * concurrent requests fine; this is NOT the broker which is one-shot).
 *
 * PLAN-PATCH P-B7: passes --game (FALLOUT4/SKYRIM_SE/...).
 */
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

export type SidecarGame =
  | "FALLOUT4"
  | "SKYRIM_SE"
  | "SKYRIM_LE"
  | "STARFIELD"
  | "OBLIVION"
  | "FALLOUT_NV";

export interface SidecarStartOptions {
  pythonPath?: string;
  modsRoot: string;
  profileDir?: string;
  game: SidecarGame;
}

interface SidecarResponse {
  jsonrpc: "2.0";
  id: number;
  result?: unknown;
  error?: { code: number; message: string };
}

export class SidecarClient {
  private proc?: ChildProcessWithoutNullStreams;
  private buffer = "";
  private pending = new Map<number, (resp: SidecarResponse) => void>();
  private nextId = 1;
  private ready = false;
  private lastStartOptions?: SidecarStartOptions;
  private restartAttempts = 0;
  private readonly maxRestarts = 3;
  private stopping = false;
  private permanentFailed = false;
  private lastExitReason?: string;

  async start(opts: SidecarStartOptions): Promise<void> {
    this.lastStartOptions = { ...opts };
    this.restartAttempts = 0;
    this.stopping = false;
    this.permanentFailed = false;
    this.lastExitReason = undefined;
    return this.launch(opts);
  }

  private async launch(opts: SidecarStartOptions): Promise<void> {
    const python = opts.pythonPath ?? "python";
    const args = [
      "-m",
      "mo2_mcp_sidecar",
      "--mods-root",
      opts.modsRoot,
      "--game",
      opts.game,
    ];
    if (opts.profileDir) {
      args.push("--profile-dir", opts.profileDir);
    }

    const proc = spawn(python, args, { stdio: ["pipe", "pipe", "pipe"] });
    this.proc = proc;
    this.buffer = "";
    this.ready = false;

    proc.stdout.on("data", (chunk) => this.onData(chunk.toString("utf8")));
    proc.stderr.on("data", (chunk) => {
      process.stderr.write(`[sidecar] ${chunk.toString("utf8")}`);
    });
    proc.on("exit", (code, signal) => this.onExit(proc, code, signal));

    return new Promise<void>((resolve, reject) => {
      let settled = false;
      const finishResolve = (): void => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve();
      };
      const finishReject = (err: Error): void => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        reject(err);
      };
      const timer = setTimeout(() => {
        finishReject(new Error("sidecar startup timeout (30s)"));
      }, 30000);

      proc.once("error", (err) => {
        finishReject(err);
      });
      proc.once("exit", (code) => {
        if (!this.ready) {
          finishReject(new Error(`sidecar exited before ready (code=${code})`));
        }
      });

      const checkReady = (): void => {
        if (settled) return;
        if (this.ready) {
          finishResolve();
          return;
        }
        setTimeout(checkReady, 50);
      };
      checkReady();
    });
  }

  private onExit(proc: ChildProcessWithoutNullStreams, code: number | null, signal: NodeJS.Signals | null): void {
    if (this.proc === proc) {
      this.ready = false;
    }
    this.lastExitReason = `code=${code}; signal=${signal}`;
    if (this.stopping || !this.lastStartOptions) return;
    if (this.restartAttempts >= this.maxRestarts) {
      this.permanentFailed = true;
      return;
    }
    this.restartAttempts += 1;
    void this.launch(this.lastStartOptions).catch((error) => {
      this.lastExitReason = error instanceof Error ? error.message : String(error);
      if (this.restartAttempts >= this.maxRestarts) {
        this.permanentFailed = true;
      }
    });
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, nl);
      this.buffer = this.buffer.slice(nl + 1);
      let msg: ({ ready?: boolean } & Partial<SidecarResponse>) | undefined;
      try {
        msg = JSON.parse(line) as { ready?: boolean } & Partial<SidecarResponse>;
      } catch {
        continue;
      }
      if (msg.ready === true) {
        this.ready = true;
        continue;
      }
      if (typeof msg.id !== "number") continue;
      const cb = this.pending.get(msg.id);
      if (cb) {
        this.pending.delete(msg.id);
        cb(msg as SidecarResponse);
      }
    }
  }

  async call(method: string, params: unknown = {}, timeoutMs = 60000): Promise<unknown> {
    if (this.permanentFailed || !this.ready || !this.proc) {
      throw new Error(this.lastExitReason ? `sidecar_not_ready: ${this.lastExitReason}` : "sidecar_not_ready");
    }
    const id = this.nextId++;
    const request = { jsonrpc: "2.0", id, method, params };
    return new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`sidecar call timeout (${method})`));
      }, timeoutMs);

      this.pending.set(id, (msg) => {
        clearTimeout(timer);
        if (msg.error) {
          reject(new Error(`sidecar error [${msg.error.code}] ${msg.error.message}`));
        } else {
          resolve(msg.result);
        }
      });

      this.proc!.stdin.write(`${JSON.stringify(request)}\n`);
    });
  }

  isReady(): boolean {
    return this.ready;
  }

  async stop(): Promise<void> {
    this.stopping = true;
    if (this.proc) {
      this.proc.stdin.end();
      await new Promise((resolve) => setTimeout(resolve, 100));
      if (this.proc.exitCode === null) {
        this.proc.kill();
      }
    }
    this.ready = false;
    this.proc = undefined;
  }
}
