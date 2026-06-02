import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { basename, join } from "node:path";
import { promisify } from "node:util";
import yaml from "js-yaml";

import type { PackManifest, PackMeta, SourceRecord } from "./types.js";

const execFileAsync = promisify(execFile);

function todayVersion(): string {
  return new Date().toISOString().slice(0, 10).replaceAll("-", ".");
}

function sortUnique(values: Iterable<string | undefined>): string[] {
  return [...new Set([...values].filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b));
}

function sortJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortJson);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, nested]) => [key, sortJson(nested)]),
    );
  }
  return value;
}

export async function readPackMeta(packRoot: string): Promise<PackMeta> {
  const defaultPackId = basename(packRoot);
  const defaults: PackMeta = {
    packId: defaultPackId,
    displayName: defaultPackId,
    version: todayVersion(),
    schemaVersion: 1,
    minPluginVersion: "0.2.0",
    owner: "unknown",
    license: "unknown",
  };

  const metaPath = join(packRoot, "bgs-kb-meta.yml");
  if (!existsSync(metaPath)) return defaults;

  const parsed = yaml.load(await readFile(metaPath, "utf8")) as Partial<PackMeta> | null;
  return { ...defaults, ...(parsed ?? {}) };
}

export async function sha256File(path: string): Promise<string> {
  const hash = createHash("sha256");
  hash.update(await readFile(path));
  return hash.digest("hex");
}

export async function readSourceCommit(packRoot: string): Promise<string | undefined> {
  try {
    const { stdout } = await execFileAsync("git", ["-C", packRoot, "rev-parse", "HEAD"]);
    const commit = stdout.trim();
    return commit.length > 0 ? commit : undefined;
  } catch {
    return undefined;
  }
}

export async function buildManifest(args: {
  packRoot: string;
  records: SourceRecord[];
  meta: PackMeta;
  builtAt: string;
  sha256: string;
}): Promise<PackManifest> {
  const sourceCommit = await readSourceCommit(args.packRoot);
  return {
    packId: args.meta.packId,
    displayName: args.meta.displayName,
    version: args.meta.version,
    schemaVersion: args.meta.schemaVersion,
    minPluginVersion: args.meta.minPluginVersion,
    owner: args.meta.owner,
    license: args.meta.license,
    ...(sourceCommit ? { sourceCommit } : {}),
    builtAt: args.builtAt,
    recordCount: args.records.length,
    domains: sortUnique(args.records.flatMap((record) => record.domains)),
    games: sortUnique(args.records.flatMap((record) => record.appliesTo.games)),
    engineFamilies: sortUnique(args.records.flatMap((record) => record.appliesTo.engineFamilies ?? [])),
    sha256: { "kb.sqlite": args.sha256 },
  };
}

export async function writeManifest(packRoot: string, manifest: PackManifest): Promise<string> {
  const manifestPath = join(packRoot, "manifest.json");
  await writeFile(manifestPath, `${JSON.stringify(sortJson(manifest), null, 2)}\n`, "utf8");
  return manifestPath;
}
