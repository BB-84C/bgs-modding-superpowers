import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createPowershellAdapter, type DaemonAdapter } from "./daemon-adapter.js";

export interface LaunchOptions {
  /** Absolute path to tools/mo2-vfs-launcher/xedit-client.ps1. */
  clientScript: string;
  /** Absolute path to xEdit.exe under .artifacts/mo2/Stock Game/.../OpenCodeXEdit/. */
  launcherPath: string;
  /** xEdit game mode, e.g. "Fallout4". */
  gameMode: string;
  /** MO2 profile name; defaults to "Default". */
  moProfile?: string;
  /** Readiness/liveness wait budget after process launch returns; defaults to 90 seconds. */
  readyTimeoutMs?: number;
  /** PowerShell executable; defaults to "pwsh". */
  pwshExe?: string;
}

export interface LaunchedDaemon {
  pid: number;
  adapter: DaemonAdapter;
  stop: () => Promise<void>;
}

/**
 * Launches the MO2-backed xEdit automation daemon via xedit-client.ps1.
 *
 * Flag names verified against tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1:
 * - process launch: --launcher-path, --game-mode, --mo-profile
 * - process wait: --xedit-pid, --timeout-seconds
 * - process stop: --xedit-pid
 *
 * process launch already calls Wait-XeditClientAutomationReady before returning;
 * the follow-up process wait call is a liveness guard for the returned PID.
 */
export async function launchDaemon(opts: LaunchOptions): Promise<LaunchedDaemon> {
  const pwsh = opts.pwshExe ?? "pwsh";
  const profile = opts.moProfile ?? "Default";

  const launchOut = await runPwshCapture(pwsh, [
    "-NoProfile",
    "-File",
    opts.clientScript,
    "process",
    "launch",
    "--launcher-path",
    opts.launcherPath,
    "--game-mode",
    opts.gameMode,
    "--mo-profile",
    profile,
  ]);

  const pid = parseLaunchPid(launchOut);
  if (!pid) throw new Error(`xedit-client process launch returned no pid: ${launchOut.slice(0, 600)}`);

  const deadline = Date.now() + (opts.readyTimeoutMs ?? 90_000);
  let ready = false;
  let lastWaitError: unknown;
  while (Date.now() < deadline) {
    try {
      const waitOut = await runPwshCapture(pwsh, [
        "-NoProfile",
        "-File",
        opts.clientScript,
        "process",
        "wait",
        "--xedit-pid",
        String(pid),
        "--timeout-seconds",
        "1",
      ]);
      if (!/^status:\s*exited\s*$/im.test(waitOut)) {
        ready = true;
        break;
      }
      lastWaitError = new Error(`Daemon exited before readiness confirmation: ${waitOut.slice(0, 400)}`);
    } catch (err) {
      lastWaitError = err;
    }
    await sleep(750);
  }
  if (!ready) {
    const detail = lastWaitError instanceof Error ? ` Last error: ${lastWaitError.message}` : "";
    throw new Error(`Daemon not ready within ${opts.readyTimeoutMs ?? 90_000} ms (pid=${pid}).${detail}`);
  }

  const adapter = createPowershellAdapter({
    clientScript: opts.clientScript,
    pid,
    scratchDir: join(tmpdir(), "xedit-mcp-calls", String(pid)),
    pwshExe: pwsh,
  });

  return {
    pid,
    adapter,
    stop: async () => {
      try {
        await runPwshCapture(pwsh, [
          "-NoProfile",
          "-File",
          opts.clientScript,
          "process",
          "stop",
          "--xedit-pid",
          String(pid),
        ]);
      } catch {
        /* best-effort shutdown for integration cleanup */
      }
    },
  };
}

function parseLaunchPid(output: string): number | undefined {
  const trimmed = output.trim();
  if (trimmed.startsWith("{")) {
    const launchRes = JSON.parse(trimmed) as {
      ok?: boolean;
      pid?: unknown;
      data?: { pid?: unknown };
      result?: { pid?: unknown };
    };
    if (!launchRes.ok && launchRes.ok !== undefined) {
      throw new Error(`xedit-client process launch refused: ${output.slice(0, 600)}`);
    }
    return normalizePid(launchRes.pid ?? launchRes.data?.pid ?? launchRes.result?.pid);
  }

  const textPid = /^xedit-pid:\s*(\d+)\s*$/im.exec(output)?.[1];
  return normalizePid(textPid);
}

function normalizePid(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) return value;
  if (typeof value === "string" && /^\d+$/.test(value)) {
    const parsed = Number.parseInt(value, 10);
    if (Number.isInteger(parsed) && parsed > 0) return parsed;
  }
  return undefined;
}

function runPwshCapture(pwsh: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(pwsh, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve(stdout);
        return;
      }
      const tail = (s: string) => s.trim().slice(-500);
      reject(
        new Error(
          `xedit-client exited ${code}.\n` +
            (stderr ? `[stderr] ${tail(stderr)}\n` : "") +
            (stdout ? `[stdout] ${tail(stdout)}\n` : ""),
        ),
      );
    });
  });
}
