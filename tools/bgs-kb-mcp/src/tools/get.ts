import { z } from "zod";

import { ok, refuse } from "../envelope/index.js";
import { KB_ERROR_CODES } from "../envelope/types.js";
import type { Envelope, Warning } from "../envelope/types.js";
import type { PackSession, SessionRegistry } from "../session/types.js";
import { GameCodeEnum, type GameCode } from "../types/enums.js";

const Args = z
  .object({
    id: z.string().min(1),
    game: GameCodeEnum.optional(),
    packId: z.string().min(1).optional(),
  })
  .strict();

export interface GetToolOptions {
  registry: SessionRegistry;
}

export interface Source {
  kind: string;
  ref?: string;
  url?: string;
  sectionPath?: string;
}

export interface GetData {
  record: Record<string, unknown>;
  mergedVariants: string[];
  appliesToRequestedGame?: boolean;
  sources: Source[];
}

interface RecordRow {
  id: string;
  pack_id: string;
  title: string;
  body_md: string;
  canonical_answer: string;
  applies_to_json: string;
  variants_json: string | null;
  query_keys_json: string | null;
  query_keys: string | null;
  domains: string | null;
  severity: string | null;
  confidence: string;
  sources_json: string;
  related_json: string | null;
  see_also_json: string | null;
  last_reviewed: string;
  schema_version: number;
}

interface FoundRecord {
  session: PackSession;
  row: RecordRow;
}

interface Variant {
  additions?: string[];
  warnings?: Array<{ code: string; severity: string; text: string }>;
  deletions?: string[];
}

class VariantDeletionUnmatched extends Error {
  constructor(
    public readonly game: string,
    public readonly target: string,
  ) {
    super(`Variant deletion target not found for ${game}: ${target}`);
  }
}

export function makeGetTool(opts: GetToolOptions) {
  return async (rawArgs: Record<string, unknown>): Promise<Envelope<GetData>> => {
    const parsed = Args.safeParse(rawArgs);
    if (!parsed.success) {
      return refuse({
        tool: "bgs_kb_get",
        summary: "Invalid bgs_kb_get request",
        code: KB_ERROR_CODES.INVALID_REQUEST,
        hint: "Pass { id } plus optional { game, packId }; no extra arguments are accepted.",
        detail: { issues: parsed.error.issues },
        severity: "MEDIUM",
      });
    }

    if (opts.registry.size === 0) {
      return refuse({
        tool: "bgs_kb_get",
        summary: "No KB packs are loaded",
        code: KB_ERROR_CODES.NOT_LOADED,
        hint: "Call bgs_kb_status to inspect discovery state, then install or enable at least one pack.",
        severity: "HIGH",
      });
    }

    const { id, game, packId } = parsed.data;
    const find = findRecordById(opts.registry, id, packId);
    if (!find.found) {
      return refuse({
        tool: "bgs_kb_get",
        summary: `Record ${id} was not found`,
        code: KB_ERROR_CODES.RECORD_NOT_FOUND,
        hint: find.hint ?? "Run bgs_kb_query first to verify the record id and pack id.",
        detail: { id, ...(packId ? { packId } : {}), ...(find.skippedPacks.length > 0 ? { skippedPacks: find.skippedPacks } : {}) },
        severity: "MEDIUM",
      });
    }

    const warnings: Warning[] = [];
    if (find.ambiguousPackIds.length > 1) {
      warnings.push({
        code: "ambiguous_record_id",
        severity: "MEDIUM",
        message: `Record id ${id} exists in multiple packs (${find.ambiguousPackIds.join(", ")}); using ${find.found.session.pack.packId}. Specify packId for deterministic lookup.`,
      });
    }
    if (find.skippedPacks.length > 0) {
      warnings.push({
        code: "skipped_non_record_packs",
        severity: "MEDIUM",
        message: `Skipped ${find.skippedPacks.length} loaded pack(s) without the standard records schema (e.g. glossary packs): ${find.skippedPacks.map((s) => s.packId).join(", ")}.`,
      });
    }

    const baseRecord = recordFromRow(find.found.row, find.found.session);
    const sources = (baseRecord.sources as Source[]) ?? [];
    if (!game) {
      return ok({
        tool: "bgs_kb_get",
        summary: `Record ${id} loaded from ${find.found.session.pack.packId}`,
        data: { record: baseRecord, mergedVariants: [], sources },
        warnings,
        status: "completed",
      });
    }

    const appliesTo = baseRecord.appliesTo as { games?: string[]; excludes?: string[] };
    if ((appliesTo.excludes ?? []).includes(game)) {
      warnings.push({ code: "game_excluded", severity: "MEDIUM", message: `Record ${id} explicitly excludes ${game}; returning the base record without variant merge.` });
      return ok({
        tool: "bgs_kb_get",
        summary: `Record ${id} does not apply to ${game}`,
        data: { record: baseRecord, mergedVariants: [], appliesToRequestedGame: false, sources },
        warnings,
        status: "completed",
      });
    }

    if (!(appliesTo.games ?? []).includes(game)) {
      warnings.push({ code: "game_not_listed", severity: "MEDIUM", message: `Record ${id} does not list ${game} in appliesTo.games; returning the base record without variant merge.` });
      return ok({
        tool: "bgs_kb_get",
        summary: `Record ${id} does not list ${game}`,
        data: { record: baseRecord, mergedVariants: [], appliesToRequestedGame: false, sources },
        warnings,
        status: "completed",
      });
    }

    const variants = (baseRecord.variants as Record<string, Variant> | undefined) ?? {};
    const variant = variants[game];
    if (!variant) {
      warnings.push({ code: "variant_not_found", severity: "MEDIUM", message: `No explicit variant for ${game}; base record returned` });
      return ok({
        tool: "bgs_kb_get",
        summary: `Record ${id} loaded from ${find.found.session.pack.packId}`,
        data: { record: baseRecord, mergedVariants: [], appliesToRequestedGame: true, sources },
        warnings,
        status: "completed",
      });
    }

    try {
      const merged = mergeVariant(baseRecord, game, variant);
      return ok({
        tool: "bgs_kb_get",
        summary: `Record ${id} loaded from ${find.found.session.pack.packId} with ${game} variant`,
        data: { record: merged, mergedVariants: [game], appliesToRequestedGame: true, sources: (merged.sources as Source[]) ?? sources },
        warnings,
        status: "completed",
      });
    } catch (error) {
      if (error instanceof VariantDeletionUnmatched) {
        return refuse({
          tool: "bgs_kb_get",
          summary: `Variant deletion target not found for ${id} (${error.game}): ${error.target}`,
          code: KB_ERROR_CODES.VARIANT_DELETION_UNMATCHED,
          hint: "Fix the KB record variant deletion target so it matches the canonical body text exactly.",
          detail: { id, game: error.game, target: error.target },
          severity: "HIGH",
          warnings,
        });
      }
      return refuse({
        tool: "bgs_kb_get",
        summary: `Unexpected bgs_kb_get failure for ${id}`,
        code: KB_ERROR_CODES.INTERNAL_ERROR,
        detail: { message: error instanceof Error ? error.message : String(error) },
        severity: "HIGH",
        warnings,
      });
    }
  };
}

// Glossary-shape packs (e.g. `bgs-l10n-starfield-zhhans`) have a `records`
// table for cross-pack compatibility but do NOT carry the standard records
// columns such as `canonical_answer`. Iterating SELECTs across all loaded
// packs blows up on the first such pack with "no such column: canonical_answer"
// or "no such table: records(_fts)?". Treat those specific errors as a
// structural "this pack isn't a records-shape pack" signal and skip it; do
// not silently swallow other SQL errors. Matches the same pattern used in
// query.ts when iterating sessions for cross-pack search.
const RECORDS_SCHEMA_MISMATCH_RE = /no such (table:\s*records(_fts)?|column:\s*canonical_answer)/i;

function findRecordById(
  registry: SessionRegistry,
  id: string,
  packId?: string,
): {
  found: FoundRecord | null;
  ambiguousPackIds: string[];
  hint?: string;
  skippedPacks: Array<{ packId: string; reason: string }>;
} {
  const skippedPacks: Array<{ packId: string; reason: string }> = [];
  if (packId) {
    const session = registry.byPackId(packId);
    if (!session) return { found: null, ambiguousPackIds: [], hint: `Pack '${packId}' is not loaded`, skippedPacks };
    try {
      const row = getRecordRow(session, id);
      return { found: row ? { session, row } : null, ambiguousPackIds: [], skippedPacks };
    } catch (err) {
      const message = (err as Error).message ?? String(err);
      if (RECORDS_SCHEMA_MISMATCH_RE.test(message)) {
        skippedPacks.push({ packId, reason: "no_records_schema" });
        return {
          found: null,
          ambiguousPackIds: [],
          hint: `Pack '${packId}' does not use the standard records schema (likely a glossary-shape pack); bgs_kb_get cannot serve it.`,
          skippedPacks,
        };
      }
      throw err;
    }
  }

  const matches: FoundRecord[] = [];
  for (const session of registry.all()) {
    try {
      const row = getRecordRow(session, id);
      if (row) matches.push({ session, row });
    } catch (err) {
      const message = (err as Error).message ?? String(err);
      if (RECORDS_SCHEMA_MISMATCH_RE.test(message)) {
        skippedPacks.push({ packId: session.pack.packId, reason: "no_records_schema" });
        continue;
      }
      throw err;
    }
  }
  return {
    found: matches[0] ?? null,
    ambiguousPackIds: matches.map((match) => match.session.pack.packId),
    skippedPacks,
  };
}

function getRecordRow(session: PackSession, id: string): RecordRow | null {
  return session.get<RecordRow>(
    `SELECT id, pack_id, title, body_md, canonical_answer, applies_to_json, variants_json,
            query_keys_json, query_keys, domains, severity, confidence, sources_json,
            related_json, see_also_json, last_reviewed, schema_version
       FROM records
       WHERE id = ?`,
    [id],
  );
}

function recordFromRow(row: RecordRow, session: PackSession): Record<string, unknown> {
  const sources = parseJsonColumn<Source[]>("sources_json", row.sources_json, []);
  return {
    id: row.id,
    packId: session.pack.packId,
    title: row.title,
    domains: domainsFromRow(row),
    appliesTo: parseJsonColumn("applies_to_json", row.applies_to_json, {}),
    canonical: { answer: row.canonical_answer, confidence: row.confidence },
    ...(row.variants_json ? { variants: parseJsonColumn("variants_json", row.variants_json, {}) } : {}),
    ...(row.query_keys_json ? { queryKeys: parseJsonColumn("query_keys_json", row.query_keys_json, []) } : {}),
    ...(row.severity ? { severity: row.severity } : {}),
    sources,
    ...(row.related_json ? { related: parseJsonColumn("related_json", row.related_json, []) } : {}),
    ...(row.see_also_json ? { seeAlso: parseJsonColumn("see_also_json", row.see_also_json, []) } : {}),
    lastReviewed: row.last_reviewed,
    schemaVersion: row.schema_version,
    bodyMd: row.body_md,
    sourcePath: sourcePathFromId(row.id),
  };
}

function domainsFromRow(row: RecordRow): string[] {
  return row.domains?.split(/\s+/).filter(Boolean) ?? [];
}

function mergeVariant(baseRecord: Record<string, unknown>, game: GameCode, variant: Variant): Record<string, unknown> {
  const merged = structuredClone(baseRecord) as Record<string, unknown>;
  let body = String(merged.bodyMd ?? "");
  for (const deletion of variant.deletions ?? []) {
    if (!body.includes(deletion)) throw new VariantDeletionUnmatched(game, deletion);
    body = body.split(deletion).join("");
  }
  const additions = variant.additions ?? [];
  const warnings = variant.warnings ?? [];
  if (additions.length > 0 || warnings.length > 0) {
    const lines = [body.trimEnd(), "", "## Game-specific notes", ""];
    for (const addition of additions) lines.push(`- ${addition}`);
    for (const warning of warnings) lines.push(`> [!WARNING] [${warning.code}|${warning.severity}] ${warning.text}`);
    body = `${lines.join("\n")}\n`;
  }
  merged.bodyMd = body;
  return merged;
}

function parseJsonColumn<T>(columnName: string, rawValue: string | null, fallback: T): T {
  if (!rawValue) return fallback;
  try {
    return JSON.parse(rawValue) as T;
  } catch (error) {
    throw new Error(`Invalid JSON in ${columnName}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function sourcePathFromId(id: string): string {
  const parts = id.split(".");
  const version = parts.pop();
  if (!version || parts.length === 0) return `records/${id}.md`;
  return `records/${parts.join("/")}.${version}.md`;
}
