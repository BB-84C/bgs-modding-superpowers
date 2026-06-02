import matter from "gray-matter";
import { readdir, readFile } from "node:fs/promises";
import { join, relative, sep } from "node:path";

import type { SourceRecord } from "./types.js";

async function walkMarkdownFiles(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const paths = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = join(root, entry.name);
      if (entry.isDirectory()) return walkMarkdownFiles(fullPath);
      if (entry.isFile() && entry.name.endsWith(".md")) return [fullPath];
      return [];
    }),
  );
  return paths.flat().sort((a, b) => a.localeCompare(b));
}

function toSourcePath(packRoot: string, filePath: string): string {
  return relative(packRoot, filePath).split(sep).join("/");
}

export async function readRecords(packRoot: string): Promise<SourceRecord[]> {
  const recordsRoot = join(packRoot, "records");
  const files = await walkMarkdownFiles(recordsRoot);
  const records: SourceRecord[] = [];

  for (const file of files) {
    const raw = await readFile(file, "utf8");
    const parsed = matter(raw);
    if (parsed.data._draft === true) continue;

    records.push({
      ...(parsed.data as Omit<SourceRecord, "bodyMd" | "sourcePath">),
      sourcePath: toSourcePath(packRoot, file),
      bodyMd: parsed.content,
    });
  }

  return records;
}
