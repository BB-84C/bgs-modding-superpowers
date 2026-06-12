import { discoverPacks, selectWinner } from "./discovery/index.js";
import type { DiscoveryResult, LoadedPack } from "./discovery/types.js";

export interface DevStatusOptions {
  json?: boolean;
  pack?: string;
  includeUserpacks?: boolean;
}

export interface FormatDevStatusOptions extends DevStatusOptions {
  context?: string;
}

type CandidateStatus = "winner" | "overridden" | "unresolved";

interface CandidatePreview {
  root: LoadedPack["root"];
  path: string;
  version: string;
  builtAt?: string;
  recordCount: number;
  status: CandidateStatus;
}

interface PackPreview {
  packId: string;
  winner?: { root: LoadedPack["root"]; path: string; builtAt?: string };
  candidates: CandidatePreview[];
}

function manifestBuiltAt(pack: LoadedPack): string | undefined {
  const value = pack.manifest.builtAt;
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function builtAtLabel(pack: LoadedPack): string {
  return manifestBuiltAt(pack) ?? "<missing>";
}

function recordsLabel(count: number): string {
  return count === 1 ? "1 record" : `${count} records`;
}

function groupCandidates(discovery: DiscoveryResult, packFilter?: string): Map<string, LoadedPack[]> {
  const source = discovery.candidates.length > 0 ? discovery.candidates : discovery.packs;
  const groups = new Map<string, LoadedPack[]>();
  for (const candidate of source) {
    if (packFilter && candidate.packId !== packFilter) continue;
    const group = groups.get(candidate.packId) ?? [];
    group.push(candidate);
    groups.set(candidate.packId, group);
  }
  return new Map([...groups.entries()].sort(([a], [b]) => a.localeCompare(b)));
}

function previewPacks(discovery: DiscoveryResult, packFilter?: string): { packs: PackPreview[]; noResolvableWinner: number } {
  const packs: PackPreview[] = [];
  let noResolvableWinner = 0;

  for (const [packId, candidates] of groupCandidates(discovery, packFilter)) {
    try {
      const { winner, losers } = selectWinner(candidates);
      const ordered = [winner, ...losers];
      packs.push({
        packId,
        winner: { root: winner.root, path: winner.packRoot, builtAt: manifestBuiltAt(winner) },
        candidates: ordered.map((candidate): CandidatePreview => ({
          root: candidate.root,
          path: candidate.packRoot,
          version: candidate.version,
          builtAt: manifestBuiltAt(candidate),
          recordCount: candidate.manifest.recordCount,
          status: candidate === winner ? "winner" : "overridden",
        })),
      });
    } catch {
      noResolvableWinner += 1;
      packs.push({
        packId,
        candidates: candidates.map((candidate): CandidatePreview => ({
          root: candidate.root,
          path: candidate.packRoot,
          version: candidate.version,
          builtAt: manifestBuiltAt(candidate),
          recordCount: candidate.manifest.recordCount,
          status: "unresolved",
        })),
      });
    }
  }

  return { packs, noResolvableWinner };
}

function formatTextPack(pack: PackPreview): string[] {
  const lines = [`  ${pack.packId}`];
  const onlySource = pack.candidates.length === 1;
  for (const candidate of pack.candidates) {
    const rootLabel = `[${candidate.root}]`.padEnd(10, " ");
    const marker = candidate.status === "winner" ? (onlySource ? "<- WINNER (only source)" : "<- WINNER") : candidate.status === "overridden" ? "(overridden)" : "(no resolvable winner)";
    lines.push(`    ${rootLabel}${candidate.path}`);
    lines.push(`              v${candidate.version}  built ${candidate.builtAt ?? "<missing>"}  ${recordsLabel(candidate.recordCount)}  ${marker}`);
  }
  return lines;
}

export function formatDevStatus(discovery: DiscoveryResult, opts: FormatDevStatusOptions = {}): string {
  const context = opts.context ?? process.argv[1] ?? "unknown";
  const { packs, noResolvableWinner } = previewPacks(discovery, opts.pack);
  const withMultipleSources = packs.filter((pack) => pack.candidates.length > 1).length;

  if (opts.json) {
    return `${JSON.stringify(
      {
        context,
        summary: {
          packs: packs.length,
          withMultipleSources,
          noResolvableWinner,
        },
        packs,
      },
      null,
      2,
    )}\n`;
  }

  const lines = [`Pack discovery preview (${context} context)`, ""];
  for (const pack of packs) {
    lines.push(...formatTextPack(pack), "");
  }
  lines.push(`Summary: ${packs.length} packs, ${withMultipleSources} with multiple sources (precedence applied), ${noResolvableWinner} with no resolvable winner.`);
  return `${lines.join("\n")}\n`;
}

export async function runDevStatus(opts: DevStatusOptions = {}): Promise<string> {
  const discovery = await discoverPacks({ userPackRoots: opts.includeUserpacks === false ? [] : undefined });
  return formatDevStatus(discovery, { ...opts, context: process.argv[1] });
}
