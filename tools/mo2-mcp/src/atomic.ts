/**
 * Atomic file write helpers — TS parallel to Python sidecar's atomic.py.
 *
 * Pattern: mkdir parent if needed -> write to sibling .tmp-XXXX -> fsync -> rename.
 * os.rename is atomic on NTFS + POSIX for same-volume same-directory renames.
 *
 * Used by every offline-path T2/T3 tool in S4/S5 (mo2_set_mod_notes,
 * mo2_edit_meta, mo2_profile_ini_set, mo2_toggle_mod, mo2_install, etc.).
 */
import { mkdir, rename, open, unlink } from "node:fs/promises";
import { dirname, extname, join } from "node:path";
import { randomBytes } from "node:crypto";

/** Atomically write text content to `path`. Creates parent dirs if missing. */
export async function atomicWriteText(
  path: string,
  content: string,
  encoding: BufferEncoding = "utf8",
): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const tmp = tempPath(path);
  try {
    const fh = await open(tmp, "w");
    try {
      await fh.writeFile(content, { encoding });
      await fh.sync();
    } finally {
      await fh.close();
    }
    await rename(tmp, path);
  } catch (err) {
    await cleanupTemp(tmp);
    throw err;
  }
}

/** Atomically write binary content to `path`. */
export async function atomicWriteBytes(path: string, content: Buffer): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const tmp = tempPath(path);
  try {
    const fh = await open(tmp, "w");
    try {
      await fh.writeFile(content);
      await fh.sync();
    } finally {
      await fh.close();
    }
    await rename(tmp, path);
  } catch (err) {
    await cleanupTemp(tmp);
    throw err;
  }
}

function tempPath(target: string): string {
  const dir = dirname(target);
  const ext = extname(target);
  const stamp = randomBytes(6).toString("hex");
  return join(dir, `.tmp-${stamp}${ext}`);
}

async function cleanupTemp(tmp: string): Promise<void> {
  try {
    await unlink(tmp);
  } catch {
    // Best effort: do not mask original write/rename error.
  }
}
