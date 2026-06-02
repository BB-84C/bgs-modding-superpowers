import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createPowershellAdapter } from "./daemon-adapter.js";
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
export async function launchDaemon(opts) {
    const pwsh = opts.pwshExe ?? "pwsh";
    const profile = opts.moProfile ?? "Default";
    const deadline = Date.now() + (opts.readyTimeoutMs ?? 180_000);
    const launchArgs = [
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
    let lastWaitErr;
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
        }
        catch (err) {
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
                const files = res.result.files;
                if (Array.isArray(files)) {
                    lastFilesCount = files.length;
                    if (files.length > 0)
                        break;
                }
            }
        }
        catch {
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
            }
            catch {
                /* best-effort */
            }
        },
    };
}
function parseLaunchPid(output) {
    const trimmed = output.trim();
    if (trimmed.startsWith("{")) {
        const launchRes = JSON.parse(trimmed);
        if (!launchRes.ok && launchRes.ok !== undefined) {
            throw new Error(`xedit-client process launch refused: ${output.slice(0, 600)}`);
        }
        return normalizePid(launchRes.pid ?? launchRes.data?.pid ?? launchRes.result?.pid);
    }
    const textPid = /^xedit-pid:\s*(\d+)\s*$/im.exec(output)?.[1];
    return normalizePid(textPid);
}
function normalizePid(value) {
    if (typeof value === "number" && Number.isInteger(value) && value > 0)
        return value;
    if (typeof value === "string" && /^\d+$/.test(value)) {
        const parsed = Number.parseInt(value, 10);
        if (Number.isInteger(parsed) && parsed > 0)
            return parsed;
    }
    return undefined;
}
function runPwshCapture(pwsh, args) {
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
            const tail = (s) => s.trim().slice(-500);
            reject(new Error(`xedit-client exited ${code}.\n` +
                (stderr ? `[stderr] ${tail(stderr)}\n` : "") +
                (stdout ? `[stdout] ${tail(stdout)}\n` : "")));
        });
    });
}
//# sourceMappingURL=launch.js.map