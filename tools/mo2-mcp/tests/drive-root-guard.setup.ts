import { readdir, stat } from "node:fs/promises";
import { parse } from "node:path";

async function rootEntries(): Promise<Set<string>> {
  const root = parse(process.cwd()).root;
  return new Set(await readdir(root));
}

async function entryDetails(name: string): Promise<string> {
  const root = parse(process.cwd()).root;
  try {
    const info = await stat(`${root}${name}`);
    const kind = info.isDirectory() ? "dir" : "file";
    return `${name} (${kind}, created=${info.birthtime.toISOString()}, modified=${info.mtime.toISOString()})`;
  } catch {
    return `${name} (entry disappeared before metadata read)`;
  }
}

export default async function driveRootGuard(): Promise<() => Promise<void>> {
  const before = await rootEntries();

  return async () => {
    const after = await rootEntries();
    const added = [...after].filter((entry) => !before.has(entry)).sort();
    if (added.length > 0) {
      const details = await Promise.all(added.map((entry) => entryDetails(entry)));
      console.error(
        `drive-root guard detected new top-level entries under ${parse(process.cwd()).root}: ${details.join(", ")}; `
          + "may also be a concurrent process; identify the owner before deleting; never auto-delete.",
      );
      process.exitCode = 1;
    }
  };
}
