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
import { spawn } from "node:child_process";
export class SidecarClient {
    proc;
    buffer = "";
    pending = new Map();
    nextId = 1;
    ready = false;
    async start(opts) {
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
        this.proc = spawn(python, args, { stdio: ["pipe", "pipe", "pipe"] });
        this.proc.stdout.on("data", (chunk) => this.onData(chunk.toString("utf8")));
        this.proc.stderr.on("data", (chunk) => {
            process.stderr.write(`[sidecar] ${chunk.toString("utf8")}`);
        });
        this.proc.on("exit", () => {
            this.ready = false;
        });
        return new Promise((resolve, reject) => {
            let settled = false;
            const finishResolve = () => {
                if (settled)
                    return;
                settled = true;
                clearTimeout(timer);
                resolve();
            };
            const finishReject = (err) => {
                if (settled)
                    return;
                settled = true;
                clearTimeout(timer);
                reject(err);
            };
            const timer = setTimeout(() => {
                finishReject(new Error("sidecar startup timeout (30s)"));
            }, 30000);
            this.proc.once("error", (err) => {
                finishReject(err);
            });
            this.proc.once("exit", (code) => {
                if (!this.ready) {
                    finishReject(new Error(`sidecar exited before ready (code=${code})`));
                }
            });
            const checkReady = () => {
                if (settled)
                    return;
                if (this.ready) {
                    finishResolve();
                    return;
                }
                setTimeout(checkReady, 50);
            };
            checkReady();
        });
    }
    onData(chunk) {
        this.buffer += chunk;
        let nl;
        while ((nl = this.buffer.indexOf("\n")) >= 0) {
            const line = this.buffer.slice(0, nl);
            this.buffer = this.buffer.slice(nl + 1);
            let msg;
            try {
                msg = JSON.parse(line);
            }
            catch {
                continue;
            }
            if (msg.ready === true) {
                this.ready = true;
                continue;
            }
            if (typeof msg.id !== "number")
                continue;
            const cb = this.pending.get(msg.id);
            if (cb) {
                this.pending.delete(msg.id);
                cb(msg);
            }
        }
    }
    async call(method, params = {}, timeoutMs = 60000) {
        if (!this.ready || !this.proc) {
            throw new Error("sidecar_not_ready");
        }
        const id = this.nextId++;
        const request = { jsonrpc: "2.0", id, method, params };
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`sidecar call timeout (${method})`));
            }, timeoutMs);
            this.pending.set(id, (msg) => {
                clearTimeout(timer);
                if (msg.error) {
                    reject(new Error(`sidecar error [${msg.error.code}] ${msg.error.message}`));
                }
                else {
                    resolve(msg.result);
                }
            });
            this.proc.stdin.write(`${JSON.stringify(request)}\n`);
        });
    }
    isReady() {
        return this.ready;
    }
    async stop() {
        if (this.proc) {
            this.proc.stdin.end();
            await new Promise((resolve) => setTimeout(resolve, 100));
            if (this.proc.exitCode === null) {
                this.proc.kill();
            }
        }
        this.ready = false;
    }
}
