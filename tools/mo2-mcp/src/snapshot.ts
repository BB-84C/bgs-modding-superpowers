/**
 * Snapshot manager — saves files before T2/T3 mutations, restores on rollback.
 *
 * Layout: <snapshotRoot>/<sessionId>/<ts>-<tool>/
 *   manifest.json  <- { snapshotId, tool, ts, files: [{source, backup}] }
 *   <flattened source path>
 *
 * Per oracle §3.4 + §3.2: snapshot before write, restore by snapshotId UUID.
 * Source path flattening: replace path separators with _ to make a flat
 * filename inside the snapshot dir; manifest carries the original path.
 */
import { cp, mkdir, readFile, readdir, stat, unlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { randomUUID } from "node:crypto";

export interface SnapshotFile {
  source: string;
  backup: string;
}

export interface SnapshotRecord {
  snapshotId: string;
  tool: string;
  ts: string;
  files: SnapshotFile[];
}

export class SnapshotManager {
  constructor(
    private snapshotRoot: string,
    private sessionId: string,
  ) {}

  /**
   * Snapshot a set of source files into a new dir under the session.
   * Returns the SnapshotRecord with snapshotId; files that don't exist
   * yet are skipped (recorded with empty backup path).
   */
  async snapshot(tool: string, sourceFiles: string[]): Promise<SnapshotRecord> {
    const snapshotId = randomUUID();
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const dir = join(this.snapshotRoot, this.sessionId, `${ts}-${tool}`);
    await mkdir(dir, { recursive: true });

    const files: SnapshotFile[] = [];
    for (const source of sourceFiles) {
      const backup = join(dir, flattenPath(source));
      try {
        await cp(source, backup, { recursive: true });
        files.push({ source, backup });
      } catch {
        files.push({ source, backup: "" });
      }
    }

    const record: SnapshotRecord = { snapshotId, tool, ts, files };
    await writeFile(join(dir, "manifest.json"), JSON.stringify(record, null, 2), "utf8");
    return record;
  }

  /**
   * Restore files from a snapshot identified by snapshotId.
   * Returns lists of restored + failed source paths.
   */
  async restore(snapshotId: string): Promise<{ restored: string[]; failed: string[] }> {
    const sessionDir = join(this.snapshotRoot, this.sessionId);
    const dirs = await readdir(sessionDir).catch(() => [] as string[]);

    for (const entry of dirs) {
      const manifestPath = join(sessionDir, entry, "manifest.json");
      try {
        const text = await readFile(manifestPath, "utf8");
        const record = JSON.parse(text) as SnapshotRecord;
        if (record.snapshotId !== snapshotId) continue;

        const restored: string[] = [];
        const failed: string[] = [];
        for (const file of record.files) {
          if (!file.backup) {
            try {
              const exists = await stat(file.source)
                .then(() => true)
                .catch(() => false);
              if (exists) await unlink(file.source);
              restored.push(file.source);
            } catch {
              failed.push(file.source);
            }
            continue;
          }

          try {
            await mkdir(dirname(file.source), { recursive: true });
            await cp(file.backup, file.source, { recursive: true, force: true });
            restored.push(file.source);
          } catch {
            failed.push(file.source);
          }
        }
        return { restored, failed };
      } catch {
        // Skip malformed or unreadable manifests.
      }
    }
    throw new Error(`snapshot_not_found: ${snapshotId}`);
  }
}

function flattenPath(source: string): string {
  return source.replace(/[/\\]/g, "_").replace(/[<>:"|?*]/g, "");
}
