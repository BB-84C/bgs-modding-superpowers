import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { spawn } from "node:child_process";

export const cleanupRoots: string[] = [];

export async function makeTempPack(prefix: string): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), prefix));
  cleanupRoots.push(root);
  return root;
}

export async function cleanupTempPacks(): Promise<void> {
  for (const root of cleanupRoots.splice(0)) {
    await rm(root, { force: true, recursive: true });
  }
}

export function recordFrontmatter(args: {
  id: string;
  title?: string;
  domains?: string[];
  games?: string[];
  engineFamilies?: string[];
  excludes?: string[];
  queryKeys?: string[];
  sources?: string;
}): string {
  const domains = args.domains ?? ["xedit"];
  const games = args.games ?? ["Fallout4"];
  const engineFamilies = args.engineFamilies ?? ["creation-engine"];
  const excludes = args.excludes ?? [];
  const queryKeys = args.queryKeys ?? [];
  const sources = args.sources ?? `sources:
  - kind: project-internal-doc
    ref: tests/unit/test-helpers.ts`;
  return `---
id: ${args.id}
title: ${args.title ?? args.id}
domains: [${domains.join(", ")}]
appliesTo:
  games: [${games.join(", ")}]
  engineFamilies: [${engineFamilies.join(", ")}]
${excludes.length > 0 ? `  excludes: [${excludes.join(", ")}]\n` : ""}canonical:
  answer: ${args.title ?? args.id} canonical answer for tests.
  confidence: verified-project-doc
${queryKeys.length > 0 ? `queryKeys: [${queryKeys.join(", ")}]\n` : ""}${sources}
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ${args.title ?? args.id}

Body content for ${args.id}.
`;
}

export async function writeRecord(packRoot: string, relativePath: string, content: string): Promise<string> {
  const recordPath = join(packRoot, "records", ...relativePath.split("/"));
  await mkdir(dirname(recordPath), { recursive: true });
  await writeFile(recordPath, content, "utf8");
  return recordPath;
}

export async function writeFixturePack(packRoot: string, records: Array<{ path: string; id: string; title?: string; domains?: string[]; games?: string[]; queryKeys?: string[] }>): Promise<void> {
  for (const record of records) {
    await writeRecord(
      packRoot,
      record.path,
      recordFrontmatter({
        id: record.id,
        title: record.title,
        domains: record.domains,
        games: record.games,
        queryKeys: record.queryKeys,
      }),
    );
  }
}

export interface CliResult {
  code: number | null;
  stdout: string;
  stderr: string;
  combined: string;
}

export async function runCli(args: string[], options: { env?: NodeJS.ProcessEnv } = {}): Promise<CliResult> {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, ["dist/cli.js", ...args], { cwd: process.cwd(), env: { ...process.env, ...options.env } });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.on("close", (code) => resolve({ code, stdout, stderr, combined: `${stdout}${stderr}` }));
  });
}
