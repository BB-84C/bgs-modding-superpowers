import { spawn } from "node:child_process";
import { writeFile, readFile, mkdir, unlink } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

export interface DaemonCall {
  command: string;
  args?: Record<string, unknown>;
  requestId?: string;
}

export type NativeEnvelope =
  | { ok: true; command: string; requestId?: string; result: unknown }
  | {
      ok: false;
      command: string;
      requestId?: string;
      error: { code: string; message: string; details?: unknown };
    };

export interface DaemonAdapter {
  call(call: DaemonCall): Promise<NativeEnvelope>;
}

export interface PowershellAdapterOptions {
  /** Absolute path to xedit-client.ps1 */
  clientScript: string;
  /** Daemon PID to target */
  pid: number;
  /** Optional mcp token to inject into every request (Batch 1: sent, daemon may ignore). */
  mcpToken?: string;
  /** Override the working directory for temp request/response files. */
  scratchDir?: string;
  /** Timeout passed to xedit-client.ps1 automation call. */
  timeoutSeconds?: number;
  pwshExe?: string;
}

/**
 * Production adapter: invokes the xedit-client.ps1 automation call subcommand with
 * file-based request/response. Flags verified against
 * tools/mo2-vfs-launcher/lib/xedit-client.call.ps1 at implementation time:
 * --xedit-pid, --request-file, --response-file, and required --timeout-seconds.
 */
export function createPowershellAdapter(opts: PowershellAdapterOptions): DaemonAdapter {
  const pwsh = opts.pwshExe ?? "pwsh";
  const timeoutSeconds = opts.timeoutSeconds ?? 30;
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
    throw new Error(`Invalid timeoutSeconds: ${opts.timeoutSeconds}. Must be a positive finite number.`);
  }
  return {
    async call({ command, args, requestId }: DaemonCall): Promise<NativeEnvelope> {
      const scratch = opts.scratchDir ?? join(tmpdir(), "xedit-mcp-calls");
      await mkdir(scratch, { recursive: true });
      const fileId = randomUUID();
      const reqPath = join(scratch, `${fileId}.req.json`);
      const resPath = join(scratch, `${fileId}.res.json`);
      const request: Record<string, unknown> = {
        command,
        args: args ?? {},
        requestId: requestId ?? fileId,
      };
      if (opts.mcpToken) request.mcpToken = opts.mcpToken;

      try {
        await writeFile(reqPath, JSON.stringify(request), "utf8");

        await runPwsh(pwsh, [
          "-NoProfile",
          "-File",
          opts.clientScript,
          // Subcommand discovered from xedit-client.ps1 dispatch.
          "automation",
          "call",
          // Flag names verified against xedit-client.call.ps1 param block.
          "--xedit-pid",
          String(opts.pid),
          "--request-file",
          reqPath,
          "--response-file",
          resPath,
          "--timeout-seconds",
          String(timeoutSeconds),
        ]);

        const raw = await readFile(resPath, "utf8");
        try {
          return JSON.parse(raw) as NativeEnvelope;
        } catch (parseErr) {
          throw new Error(
            `Daemon response at ${resPath} was not valid JSON: ${(parseErr as Error).message}. ` +
              `First 200 bytes: ${raw.slice(0, 200)}`,
          );
        }
      } finally {
        // Best-effort cleanup so the token-bearing request file never lingers.
        await unlink(reqPath).catch(() => {});
        await unlink(resPath).catch(() => {});
      }
    },
  };
}

function runPwsh(pwsh: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(pwsh, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      const tail = (s: string) => s.trim().slice(-500);
      reject(
        new Error(
          `xedit-client.ps1 exited ${code}.\n` +
            (stderr ? `[stderr] ${tail(stderr)}\n` : "") +
            (stdout ? `[stdout] ${tail(stdout)}\n` : ""),
        ),
      );
    });
  });
}
