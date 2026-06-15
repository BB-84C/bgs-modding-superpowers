import { createHash } from "node:crypto";
import { mkdir, readFile, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";
export const LEASE_LOCK_TTL_MS = 10 * 60 * 1000;
export function computeLeaseTargetHash(targets) {
    return createHash("sha256")
        .update(JSON.stringify(targets.map((target) => target.path).sort()))
        .digest("hex");
}
export function computeLeaseTargetPathHash(path) {
    return createHash("sha256").update(JSON.stringify(path)).digest("hex");
}
export function computeLeaseTargetHashes(targets) {
    return [...new Set(targets.map((target) => target.path))]
        .sort()
        .map((path) => computeLeaseTargetPathHash(path));
}
function leasesDir(mo2Root) {
    return join(mo2Root, ".mo2-mcp", "leases");
}
export function leaseLockPath(mo2Root, targetHash) {
    return join(leasesDir(mo2Root), `${targetHash}.lock`);
}
function isEnoent(error) {
    return error?.code === "ENOENT";
}
function isEexist(error) {
    return error?.code === "EEXIST";
}
function parseLock(raw) {
    try {
        const parsed = JSON.parse(raw);
        if (typeof parsed.plan_id !== "string" ||
            typeof parsed.mcp_pid !== "number" ||
            typeof parsed.mcp_session_id !== "string" ||
            typeof parsed.lease_token !== "string" ||
            typeof parsed.tool_name !== "string" ||
            typeof parsed.created_at !== "string" ||
            typeof parsed.expires_at !== "string") {
            return null;
        }
        return parsed;
    }
    catch {
        return null;
    }
}
function holderFrom(metadata) {
    return {
        mcp_pid: metadata.mcp_pid,
        created_at: metadata.created_at,
        tool_name: metadata.tool_name,
    };
}
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
async function readExistingLock(path) {
    for (let attempt = 0; attempt < 4; attempt++) {
        try {
            const parsed = parseLock(await readFile(path, "utf8"));
            if (parsed)
                return parsed;
            if (attempt < 3) {
                await sleep(100);
                continue;
            }
            return null;
        }
        catch (error) {
            if (isEnoent(error))
                return null;
            throw error;
        }
    }
    return null;
}
async function removeLockIfPresent(path) {
    try {
        await unlink(path);
    }
    catch (error) {
        if (!isEnoent(error))
            throw error;
    }
}
function parseTasklistCsvPid(line) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("INFO:"))
        return null;
    const quoted = /^"[^"]+","(\d+)"/.exec(trimmed);
    if (quoted)
        return Number(quoted[1]);
    const fields = trimmed.split(",");
    if (fields.length > 1) {
        const pid = Number(fields[1].replaceAll('"', "").trim());
        return Number.isInteger(pid) ? pid : null;
    }
    return null;
}
export async function isPidAlive(pid) {
    if (!Number.isInteger(pid) || pid <= 0)
        return false;
    if (process.platform === "win32") {
        try {
            const childProcess = await import("node:child_process");
            if (typeof childProcess.execFile !== "function")
                return isPidAliveWithSignal(pid);
            const execFileAsync = promisify(childProcess.execFile);
            const { stdout } = await execFileAsync("tasklist", ["/FI", `PID eq ${pid}`, "/FO", "CSV", "/NH"], { windowsHide: true });
            return stdout
                .split(/\r?\n/)
                .some((line) => parseTasklistCsvPid(line) === pid);
        }
        catch {
            return false;
        }
    }
    return isPidAliveWithSignal(pid);
}
function isPidAliveWithSignal(pid) {
    try {
        process.kill(pid, 0);
        return true;
    }
    catch (error) {
        return error?.code === "EPERM";
    }
}
export async function acquireLeaseLock(mo2Root, targetHash, metadata, options = {}) {
    await mkdir(leasesDir(mo2Root), { recursive: true });
    const path = leaseLockPath(mo2Root, targetHash);
    const lockBody = `${JSON.stringify(metadata, null, 2)}\n`;
    const pidAlive = options.isPidAlive ?? isPidAlive;
    for (let attempt = 0; attempt < 5; attempt++) {
        try {
            await writeFile(path, lockBody, { encoding: "utf8", flag: "wx" });
            return { acquired: true, lockPath: path };
        }
        catch (error) {
            if (!isEexist(error))
                throw error;
        }
        const existing = await readExistingLock(path);
        if (!existing) {
            await removeLockIfPresent(path);
            continue;
        }
        const expiresAtMs = Date.parse(existing.expires_at);
        const expired = !Number.isFinite(expiresAtMs) || expiresAtMs <= Date.now();
        const alive = expired ? true : await pidAlive(existing.mcp_pid);
        if (expired || !alive) {
            await removeLockIfPresent(path);
            continue;
        }
        return { acquired: false, lockPath: path, holder: holderFrom(existing) };
    }
    const existing = await readExistingLock(path);
    if (existing)
        return { acquired: false, lockPath: path, holder: holderFrom(existing) };
    await writeFile(path, lockBody, { encoding: "utf8", flag: "wx" });
    return { acquired: true, lockPath: path };
}
export async function acquireLeasesForTargets(mo2Root, targets, metadata, options = {}) {
    const targetHashes = computeLeaseTargetHashes(targets);
    const acquiredHashes = [];
    const lockPaths = [];
    for (const targetHash of targetHashes) {
        const acquired = await acquireLeaseLock(mo2Root, targetHash, metadata, options);
        if (!acquired.acquired) {
            await releaseLeaseLocks(mo2Root, acquiredHashes, metadata.plan_id);
            return {
                acquired: false,
                holders: [acquired.holder],
                acquiredLocks: acquiredHashes,
                targetHashes,
            };
        }
        acquiredHashes.push(targetHash);
        lockPaths.push(acquired.lockPath);
    }
    return { acquired: true, lockPaths, targetHashes };
}
export async function releaseLeaseLock(mo2Root, targetHash, planId) {
    const path = leaseLockPath(mo2Root, targetHash);
    const existing = await readExistingLock(path);
    if (!existing)
        return;
    if (existing.plan_id !== planId)
        return;
    await removeLockIfPresent(path);
}
export async function releaseLeaseLocks(mo2Root, targetHashes, planId) {
    await Promise.all(targetHashes.map((targetHash) => releaseLeaseLock(mo2Root, targetHash, planId)));
}
