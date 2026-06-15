/**
 * Lease verifier — content-hash + structural-fingerprint based optimistic locking.
 *
 * Per oracle §3.2: NTFS mtime is unreliable (lazy update, 1s rounding in some
 * Python APIs). For text files we hash content. For directories we use file
 * count + total size as a structural fingerprint (still O(walk) but stable).
 *
 * Plan computes lease at planning time; apply re-computes + compares before
 * mutating. Drift → lease_violation, caller re-plans against fresh state.
 */
import { readFile, stat, readdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";

export interface LeaseComponent {
  path: string;
  kind: "text-file" | "directory";
  /** Set for text-file: sha256 of full content. */
  contentHash?: string;
  /** Set for text-file: byte length. */
  size?: number;
  /** Set for directory: count of files (recursively). */
  fileCount?: number;
  /** Set for directory: sum of file sizes (bytes). */
  totalSize?: number;
}

export interface Lease {
  token: string;
  components: LeaseComponent[];
}

export interface LeaseTarget {
  path: string;
  kind: "text-file" | "directory";
}

export async function fingerprintFile(path: string): Promise<LeaseComponent> {
  try {
    const content = await readFile(path);
    const contentHash = createHash("sha256").update(content).digest("hex");
    return { path, kind: "text-file", contentHash, size: content.length };
  } catch (e) {
    if (
      e instanceof Error &&
      "code" in e &&
      (e as NodeJS.ErrnoException).code === "ENOENT"
    ) {
      return { path, kind: "text-file", contentHash: "missing", size: 0 };
    }
    throw e;
  }
}

export async function fingerprintDir(path: string): Promise<LeaseComponent> {
  let fileCount = 0;
  let totalSize = 0;

  async function walk(d: string): Promise<void> {
    const entries = await readdir(d, { withFileTypes: true });
    for (const e of entries) {
      const full = join(d, e.name);
      if (e.isDirectory()) {
        await walk(full);
      } else {
        fileCount++;
        try {
          const s = await stat(full);
          totalSize += s.size;
        } catch {
          // skip unreadable files
        }
      }
    }
  }

  try {
    await walk(path);
  } catch (e) {
    if (
      e instanceof Error &&
      "code" in e &&
      (e as NodeJS.ErrnoException).code === "ENOENT"
    ) {
      return { path, kind: "directory", fileCount: 0, totalSize: 0 };
    }
    throw e;
  }
  return { path, kind: "directory", fileCount, totalSize };
}

export async function computeLease(targets: LeaseTarget[]): Promise<Lease> {
  const components = await Promise.all(
    targets.map((t) =>
      t.kind === "text-file" ? fingerprintFile(t.path) : fingerprintDir(t.path),
    ),
  );
  const token = createHash("sha256")
    .update(JSON.stringify(components))
    .digest("hex");
  return { token, components };
}

export interface LeaseDrift {
  path: string;
  planComponent: LeaseComponent;
  currentComponent: LeaseComponent;
}

export async function verifyLease(
  lease: Lease,
): Promise<{ valid: true } | { valid: false; drift: LeaseDrift[] }> {
  const drift: LeaseDrift[] = [];
  for (const planComp of lease.components) {
    const current =
      planComp.kind === "text-file"
        ? await fingerprintFile(planComp.path)
        : await fingerprintDir(planComp.path);
    if (JSON.stringify(current) !== JSON.stringify(planComp)) {
      drift.push({
        path: planComp.path,
        planComponent: planComp,
        currentComponent: current,
      });
    }
  }
  if (drift.length === 0) return { valid: true };
  return { valid: false, drift };
}
