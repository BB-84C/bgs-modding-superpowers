import { spawn } from "node:child_process";
import { writeFile, readFile, mkdir, unlink } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
/**
 * Production adapter: invokes the xedit-client.ps1 automation call subcommand with
 * file-based request/response. Flags verified against
 * tools/mo2-vfs-launcher/lib/xedit-client.call.ps1 at implementation time:
 * --xedit-pid, --request-file, --response-file, and required --timeout-seconds.
 */
export function createPowershellAdapter(opts) {
    const pwsh = opts.pwshExe ?? "pwsh";
    const timeoutSeconds = opts.timeoutSeconds ?? 30;
    if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
        throw new Error(`Invalid timeoutSeconds: ${opts.timeoutSeconds}. Must be a positive finite number.`);
    }
    return {
        async call({ command, args, requestId }) {
            const scratch = opts.scratchDir ?? join(tmpdir(), "xedit-mcp-calls");
            await mkdir(scratch, { recursive: true });
            const fileId = randomUUID();
            const reqPath = join(scratch, `${fileId}.req.json`);
            const resPath = join(scratch, `${fileId}.res.json`);
            const request = {
                command,
                args: args ?? {},
                requestId: requestId ?? fileId,
            };
            if (opts.mcpToken)
                request.mcpToken = opts.mcpToken;
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
                // xEdit writes the response file as UTF-8 *with BOM* on Windows; strip the
                // leading 0xFEFF so JSON.parse doesn't choke on the first byte.
                const stripped = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
                try {
                    return JSON.parse(stripped);
                }
                catch (parseErr) {
                    throw new Error(`Daemon response at ${resPath} was not valid JSON: ${parseErr.message}. ` +
                        `First 200 bytes: ${stripped.slice(0, 200)}`);
                }
            }
            finally {
                // Best-effort cleanup so the token-bearing request file never lingers.
                await unlink(reqPath).catch(() => { });
                await unlink(resPath).catch(() => { });
            }
        },
    };
}
function runPwsh(pwsh, args) {
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
            const tail = (s) => s.trim().slice(-500);
            reject(new Error(`xedit-client.ps1 exited ${code}.\n` +
                (stderr ? `[stderr] ${tail(stderr)}\n` : "") +
                (stdout ? `[stdout] ${tail(stdout)}\n` : "")));
        });
    });
}
//# sourceMappingURL=daemon-adapter.js.map