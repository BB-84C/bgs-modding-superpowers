import { createHash } from "node:crypto";
import { mkdir, readFile, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";
import type { LeaseTarget } from "./lease.js";

export const LEASE_LOCK_TTL_MS = 10 * 60 * 1000;

export interface LeaseLockMetadata {
  plan_id: string;
  mcp_pid: number;
  mcp_session_id: string;
  lease_token: string;
  tool_name: string;
  created_at: string;
  expires_at: string;
}

export interface LeaseLockHolder {
  mcp_pid: number;
  created_at: string;
  tool_name: string;
}

export type LeaseLockAcquireResult =
  | { acquired: true; lockPath: string }
  | { acquired: false; lockPath: string; holder: LeaseLockHolder };

export interface LeaseLockAcquireOptions {
  isPidAlive?: (pid: number) => Promise<boolean>;
}

export function computeLeaseTargetHash(targets: LeaseTarget[]): string {
  return createHash("sha256")
    .update(JSON.stringify(targets.map((target) => target.path).sort()))
    .digest("hex");
}

function leasesDir(mo2Root: string): string {
  return join(mo2Root, ".mo2-mcp", "leases");
}

export function leaseLockPath(mo2Root: string, targetHash: string): string {
  return join(leasesDir(mo2Root), `${targetHash}.lock`);
}

function isEnoent(error: unknown): boolean {
  return (error as NodeJS.ErrnoException | undefined)?.code === "ENOENT";
}

function isEexist(error: unknown): boolean {
  return (error as NodeJS.ErrnoException | undefined)?.code === "EEXIST";
}

function parseLock(raw: string): LeaseLockMetadata | null {
  try {
    const parsed = JSON.parse(raw) as Partial<LeaseLockMetadata>;
    if (
      typeof parsed.plan_id !== "string" ||
      typeof parsed.mcp_pid !== "number" ||
      typeof parsed.mcp_session_id !== "string" ||
      typeof parsed.lease_token !== "string" ||
      typeof parsed.tool_name !== "string" ||
      typeof parsed.created_at !== "string" ||
      typeof parsed.expires_at !== "string"
    ) {
      return null;
    }
    return parsed as LeaseLockMetadata;
  } catch {
    return null;
  }
}

function holderFrom(metadata: LeaseLockMetadata): LeaseLockHolder {
  return {
    mcp_pid: metadata.mcp_pid,
    created_at: metadata.created_at,
    tool_name: metadata.tool_name,
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readExistingLock(path: string): Promise<LeaseLockMetadata | null> {
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const parsed = parseLock(await readFile(path, "utf8"));
      if (parsed) return parsed;
      if (attempt < 3) {
        await sleep(100);
        continue;
      }
      return null;
    } catch (error) {
      if (isEnoent(error)) return null;
      throw error;
    }
  }
  return null;
}

async function removeLockIfPresent(path: string): Promise<void> {
  try {
    await unlink(path);
  } catch (error) {
    if (!isEnoent(error)) throw error;
  }
}

function parseTasklistCsvPid(line: string): number | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("INFO:")) return null;
  const quoted = /^"[^"]+","(\d+)"/.exec(trimmed);
  if (quoted) return Number(quoted[1]);
  const fields = trimmed.split(",");
  if (fields.length > 1) {
    const pid = Number(fields[1].replaceAll('"', "").trim());
    return Number.isInteger(pid) ? pid : null;
  }
  return null;
}

export async function isPidAlive(pid: number): Promise<boolean> {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  if (process.platform === "win32") {
    try {
      const childProcess = await import("node:child_process");
      if (typeof childProcess.execFile !== "function") return isPidAliveWithSignal(pid);
      const execFileAsync = promisify(childProcess.execFile);
      const { stdout } = await execFileAsync(
        "tasklist",
        ["/FI", `PID eq ${pid}`, "/FO", "CSV", "/NH"],
        { windowsHide: true },
      );
      return stdout
        .split(/\r?\n/)
        .some((line) => parseTasklistCsvPid(line) === pid);
    } catch {
      return false;
    }
  }

  return isPidAliveWithSignal(pid);
}

function isPidAliveWithSignal(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException | undefined)?.code === "EPERM";
  }
}

export async function acquireLeaseLock(
  mo2Root: string,
  targetHash: string,
  metadata: LeaseLockMetadata,
  options: LeaseLockAcquireOptions = {},
): Promise<LeaseLockAcquireResult> {
  await mkdir(leasesDir(mo2Root), { recursive: true });
  const path = leaseLockPath(mo2Root, targetHash);
  const lockBody = `${JSON.stringify(metadata, null, 2)}\n`;
  const pidAlive = options.isPidAlive ?? isPidAlive;

  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      await writeFile(path, lockBody, { encoding: "utf8", flag: "wx" });
      return { acquired: true, lockPath: path };
    } catch (error) {
      if (!isEexist(error)) throw error;
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
  if (existing) return { acquired: false, lockPath: path, holder: holderFrom(existing) };
  await writeFile(path, lockBody, { encoding: "utf8", flag: "wx" });
  return { acquired: true, lockPath: path };
}

export async function releaseLeaseLock(
  mo2Root: string,
  targetHash: string,
  planId: string,
): Promise<void> {
  const path = leaseLockPath(mo2Root, targetHash);
  const existing = await readExistingLock(path);
  if (!existing) return;
  if (existing.plan_id !== planId) return;
  await removeLockIfPresent(path);
}
