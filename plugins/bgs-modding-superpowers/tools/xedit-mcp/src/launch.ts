import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createPowershellAdapter, type DaemonAdapter } from "./daemon-adapter.js";

/**
 * Launch options for the broker / OpenCodeVfsLauncher path.
 *
 * Why this path: `xedit-client.ps1 process launch` is the canonical outer client.
 * Internally it goes through the MO2 control-plane live bridge (which must already
 * be running — i.e. MO2 must be alive with the Mo2AgentControl plugin loaded so the
 * bootstrap files at `<MO2_Root>/plugins/Mo2AgentControl/bootstrap/runtime/`
 * exist). The harness assumption is: caller starts MO2 first, then calls
 * `launchDaemon` to spawn the xEdit-as-tool inside that MO2 session.
 */
export interface LaunchOptions {
  /** Absolute path to tools/mo2-vfs-launcher/xedit-client.ps1. */
  clientScript: string;
  /** Absolute path to xEdit.exe; typically under `<MO2_Root>/tools/xEdit/`. */
  launcherPath: string;
  /** xEdit game mode, e.g. "Fallout4". */
  gameMode: string;
  /** MO2 profile name; defaults to "Default". */
  moProfile?: string;
  /**
   * Absolute path to the Data directory xEdit should use (passed as `-D:`).
   * If omitted, xEdit auto-discovers the game install via the Windows
   * registry — which on Steam-installed games points at the Steam library,
   * NOT MO2's Stock Game. ALWAYS pass this when the agent wants xEdit to
   * see the MO2-managed game tree. Read MO2's ModOrganizer.ini gamePath +
   * "\\Data" for the canonical answer.
   */
  dataPath?: string;
  /**
   * Absolute path to a custom plugins.txt (passed as `-P:`). If omitted,
   * xedit-client.ps1 derives a session plugins file from the MO2 profile
   * (default) or from the `--plugin` repeat-args. Agents writing
   * experimental load orders should generate a plugins.txt under
   * `.opencode/artifacts/<task>/plugins.txt` and pass it here.
   * See: skills/writing-bgs-load-order/SKILL.md for the file format.
   */
  pluginsFile?: string;
  /** Total wait budget for daemon-ready + plugins-loaded; defaults to 180 seconds. */
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
 * Launches the MO2-backed xEdit automation daemon via `xedit-client.ps1 process launch`
 * and waits for both daemon readiness AND plugins-loaded confirmation.
 *
 * Flag names verified against `tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1`:
 *  - process launch: --launcher-path, --game-mode, --mo-profile
 *  - process wait:   --xedit-pid, --timeout-seconds
 *  - process stop:   --xedit-pid
 *
 * Plugin-load wait: `process launch` returns as soon as the daemon accepts a pipe
 * connection (system.describe ok), but xEdit may still be loading plugins. We poll
 * `files.list` here until either it reports a non-empty load order or the deadline
 * passes. A daemon that reports 0 plugins after the full budget is still returned —
 * the integration test can then surface that as a semantic failure.
 */
export async function launchDaemon(opts: LaunchOptions): Promise<LaunchedDaemon> {
  const pwsh = opts.pwshExe ?? "pwsh";
  const profile = opts.moProfile ?? "Default";
  const deadline = Date.now() + (opts.readyTimeoutMs ?? 180_000);

  const launchArgs: string[] = [
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
  ];
  if (opts.dataPath) {
    launchArgs.push("--data-path", opts.dataPath);
  }
  if (opts.pluginsFile) {
    launchArgs.push("--plugins-file", opts.pluginsFile);
  }
  const launchOut = await runPwshCapture(pwsh, launchArgs);

  const pid = parseLaunchPid(launchOut);
  if (!pid) {
    throw new Error(`xedit-client process launch returned no pid: ${launchOut.slice(0, 600)}`);
  }

  // Phase A: process wait until the daemon answers (or refuses with exited).
  let dwReady = false;
  let lastWaitErr: unknown;
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
        dwReady = true;
        break;
      }
      lastWaitErr = new Error(`Daemon exited before readiness confirmation: ${waitOut.slice(0, 400)}`);
    } catch (err) {
      lastWaitErr = err;
    }
    await sleep(750);
  }
  if (!dwReady) {
    const detail = lastWaitErr instanceof Error ? ` Last error: ${lastWaitErr.message}` : "";
    throw new Error(`Daemon not ready within ${opts.readyTimeoutMs ?? 180_000} ms (pid=${pid}).${detail}`);
  }

  const adapter = createPowershellAdapter({
    clientScript: opts.clientScript,
    pid,
    scratchDir: join(tmpdir(), "xedit-mcp-calls", String(pid)),
    pwshExe: pwsh,
  });

  // Phase B: poll files.list until it reports a non-empty load order.
  // xEdit may serve the pipe before plugin load completes; this guards against the race.
  let lastFilesCount = 0;
  while (Date.now() < deadline) {
    try {
      const res = await adapter.call({ command: "files.list", args: {} });
      if (res.ok) {
        const files = (res.result as { files?: unknown }).files;
        if (Array.isArray(files)) {
          lastFilesCount = files.length;
          if (files.length > 0) break;
        }
      }
    } catch {
      /* swallow; we'll keep polling */
    }
    await sleep(1_500);
  }
  // Note: returns even if lastFilesCount is still 0 after the budget — the caller
  // sees an empty load order via xedit_session and the integration test fails the
  // appropriate assertion with the empty envelope captured as semantic-RED evidence.

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
        /* best-effort */
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
