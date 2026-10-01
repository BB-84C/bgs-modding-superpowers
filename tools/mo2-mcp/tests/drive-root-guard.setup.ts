import { readdir } from "node:fs/promises";
import { parse } from "node:path";

async function rootEntries(): Promise<Set<string>> {
  const root = parse(process.cwd()).root;
  return new Set(await readdir(root));
}

export default async function driveRootGuard(): Promise<() => Promise<void>> {
  const before = await rootEntries();

  return async () => {
    const after = await rootEntries();
    const added = [...after].filter((entry) => !before.has(entry)).sort();
    if (added.length > 0) {
      throw new Error(
        `drive-root guard detected new top-level entries under ${parse(process.cwd()).root}: ${added.join(", ")}`,
      );
    }
  };
}
