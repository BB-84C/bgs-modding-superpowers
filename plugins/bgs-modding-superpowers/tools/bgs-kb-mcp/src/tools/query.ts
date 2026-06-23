import { performance } from "node:perf_hooks";
import { z } from "zod";

import { ok, refuse } from "../envelope/index.js";
import { KB_ERROR_CODES } from "../envelope/types.js";
import type { Envelope } from "../envelope/types.js";
import type { PackSession, SessionRegistry } from "../session/types.js";
import { DomainEnum, GameCodeEnum, type GameCode } from "../types/enums.js";
import { sanitizeFtsQuery } from "./sanitize.js";

const MAX_RESULTS_DEFAULT = 5;
const MAX_RESULTS_CAP_DEFAULT = 20;

const Args = z
  .object({
    query: z.string(),
    games: z.array(GameCodeEnum).optional(),
    domains: z.array(DomainEnum).optional(),
    toolchains: z.array(z.string()).optional(),
    kinds: z.array(z.enum(["rule", "workflow", "gotcha", "explanation", "source-map"])).optional(),
    packIds: z.array(z.string()).optional(),
    maxResults: z.number().int().min(1).optional(),
    detailLevel: z.enum(["summary", "expanded"]).optional(),
    includeVariants: z.boolean().optional(),
    includeSources: z.boolean().optional(),
    cursor: z.string().optional(),
  })
  .strict();

export interface QueryToolOptions {
  registry: SessionRegistry;
  /** Hard cap; default 20 per spec. */
  maxResultsCap?: number;
}

export interface QueryHit {
  id: string;
  packId: string;
  title: string;
  score: number;
  kind?: string;
  appliesTo: { games: string[]; engineFamilies: string[] };
  synopsis: string;
  snippet?: string;
  bodyExcerpt?: string;
  variantNotes?: Array<{ game: string; text: string }>;
  sources?: Array<{ kind: string; ref?: string; url?: string }>;
  recordRef: { pack: string; path: string };
}

export interface QueryData {
  normalizedQuery: Record<string, unknown>;
  hits: QueryHit[];
  stats: {
    kbVersionMap: Record<string, string>;
    elapsedMs: number;
    totalCandidates: number;
  };
  nextCursor: string | null;
}

interface QueryRow {
  id: string;
  title: string;
  canonical_answer: string;
  body_md: string;
  applies_to_json: string;
  variants_json: string | null;
  sources_json: string;
  pack_id: string;
  snippet: string | null;
  rank: number;
}

interface VariantValue {
  additions?: string[];
  warnings?: Array<{ code: string; severity: string; text: string }>;
}

interface Candidate {
  hit: QueryHit;
  rank: number;
}

export function makeQueryTool(opts: QueryToolOptions) {
  return async (rawArgs: Record<string, unknown>): Promise<Envelope<QueryData>> => {
    const started = performance.now();
    const parsed = Args.safeParse(rawArgs);
    if (!parsed.success) {
      return refuse({
        tool: "bgs_kb_query",
        summary: "Invalid bgs_kb_query request",
        code: KB_ERROR_CODES.INVALID_REQUEST,
        hint: "Provide a non-empty query string and only documented bgs_kb_query arguments.",
        detail: { issues: parsed.error.issues },
        severity: "MEDIUM",
      });
    }

    const query = parsed.data.query.trim();
    const sanitizedQuery = sanitizeFtsQuery(query);
    if (query.length === 0 || sanitizedQuery.length === 0) {
      return refuse({
        tool: "bgs_kb_query",
        summary: "Invalid bgs_kb_query request: query must not be empty",
        code: KB_ERROR_CODES.INVALID_REQUEST,
        hint: "Pass a query containing at least one searchable term.",
        severity: "MEDIUM",
      });
    }

    if (opts.registry.size === 0) {
      return refuse({
        tool: "bgs_kb_query",
        summary: "No KB packs are loaded",
        code: KB_ERROR_CODES.NOT_LOADED,
        hint: "Call bgs_kb_status to inspect discovery state, then install or enable at least one pack.",
        severity: "HIGH",
      });
    }

    const cap = opts.maxResultsCap ?? MAX_RESULTS_CAP_DEFAULT;
    const maxResults = Math.min(parsed.data.maxResults ?? MAX_RESULTS_DEFAULT, cap);
    const overfetchLimit = Math.max(maxResults * 2, 20);
    const packFilter = new Set(parsed.data.packIds ?? []);
    const sessions = opts.registry.all().filter((session) => packFilter.size === 0 || packFilter.has(session.pack.packId));
    const kbVersionMap = Object.fromEntries(opts.registry.all().map((session) => [session.pack.packId, session.pack.version]));
    const candidates: Candidate[] = [];
    // Track packs the query had to skip because they don't share the
    // standard records / records_fts schema (e.g. the glossary-schema pack
    // `bgs-l10n-starfield-zhhans`). Surfaced in the response stats so the
    // agent can see why a cross-pack search returned narrower-than-expected
    // results. Captured in memory/45 KB Workflow Scope Split (2026-06-12)
    // and 2026-06-11 known follow-up note about `no such table: records_fts`.
    const skippedPacks: Array<{ packId: string; reason: string }> = [];

    for (const session of sessions) {
      let rows: QueryRow[];
      try {
        rows = querySession(session, sanitizedQuery, {
          games: parsed.data.games,
          domains: parsed.data.domains,
          limit: overfetchLimit,
        });
        if (rows.length === 0) {
          const fallbackQuery = orFallbackQuery(sanitizedQuery);
          if (fallbackQuery !== sanitizedQuery) {
            rows = querySession(session, fallbackQuery, {
              games: parsed.data.games,
              domains: parsed.data.domains,
              limit: overfetchLimit,
            });
          }
        }
      } catch (err) {
        // Glossary-schema packs (e.g. bgs-l10n-starfield-zhhans) do not have
        // the standard `records` / `records_fts` tables. SQLite throws
        // `no such table: records_fts` (or `no such table: records`) on the
        // FTS query. Skip the pack instead of failing the entire cross-pack
        // search. Other SQL errors are NOT silently swallowed — only the
        // missing-records-schema case is treated as a structural skip.
        const message = (err as Error).message ?? String(err);
        if (/no such (table:\s*records(_fts)?|column:\s*canonical_answer)/i.test(message)) {
          skippedPacks.push({ packId: session.pack.packId, reason: "no_records_schema" });
          continue;
        }
        throw err;
      }
      for (const row of rows) {
        candidates.push({
          rank: row.rank,
          hit: rowToHit(row, session, {
            score: scoreRow(row, sanitizedQuery),
            detailLevel: parsed.data.detailLevel ?? "summary",
            includeSources: parsed.data.includeSources ?? true,
            includeVariants: parsed.data.includeVariants ?? true,
            games: parsed.data.games,
          }),
        });
      }
    }

    candidates.sort((a, b) => b.hit.score - a.hit.score || a.hit.packId.localeCompare(b.hit.packId) || a.hit.id.localeCompare(b.hit.id));
    const hits = candidates.slice(0, maxResults).map((candidate) => candidate.hit);
    const elapsedMs = Math.max(0, performance.now() - started);

    return ok({
      tool: "bgs_kb_query",
      summary: `${hits.length} hit(s) for '${query}' across ${sessions.length} pack(s)`,
      data: {
        normalizedQuery: {
          query,
          fts: sanitizedQuery,
          games: parsed.data.games ?? null,
          domains: parsed.data.domains ?? null,
          packIds: parsed.data.packIds ?? null,
          maxResults,
          detailLevel: parsed.data.detailLevel ?? "summary",
          cursorIgnored: parsed.data.cursor ?? null,
        },
        hits,
        stats: {
          kbVersionMap,
          elapsedMs,
          totalCandidates: candidates.length,
          // skippedPacks is empty in the standard case. Populated when one or
          // more loaded packs ship a non-records schema (e.g. glossary packs);
          // see the per-session try/catch in the query loop above.
          skippedPacks: skippedPacks.length > 0 ? skippedPacks : undefined,
        },
        // Cursor support is intentionally stubbed in v1. Agents should refine
        // queries rather than page broad searches until KB-6 adds real cursors.
        nextCursor: null,
      },
      status: "completed",
    });
  };
}

function querySession(
  session: PackSession,
  ftsQuery: string,
  opts: { games?: string[]; domains?: string[]; limit: number },
): QueryRow[] {
  const clauses = ["records_fts MATCH ?"];
  const params: unknown[] = [ftsQuery];

  if (opts.games && opts.games.length > 0) {
    const placeholders = placeholdersFor(opts.games);
    clauses.push(`records.id IN (SELECT record_id FROM record_games WHERE game IN (${placeholders}))`);
    params.push(...opts.games);
    clauses.push(`records.id NOT IN (SELECT record_id FROM record_excludes WHERE game IN (${placeholders}))`);
    params.push(...opts.games);
  }

  if (opts.domains && opts.domains.length > 0) {
    clauses.push(`records.id IN (SELECT record_id FROM record_domains WHERE domain IN (${placeholdersFor(opts.domains)}))`);
    params.push(...opts.domains);
  }

  params.push(opts.limit);
  return session.all<QueryRow>(
    `SELECT records.id, records.title, records.canonical_answer, records.body_md,
       records.applies_to_json, records.variants_json, records.sources_json,
       records.pack_id,
       snippet(records_fts, 1, '[', ']', '…', 16) AS snippet,
       bm25(records_fts, 6.0, 1.0, 8.0, 2.0) AS rank
     FROM records
     JOIN records_fts ON records.rowid = records_fts.rowid
     WHERE ${clauses.join(" AND ")}
     ORDER BY rank
     LIMIT ?`,
    params,
  );
}

function orFallbackQuery(ftsQuery: string): string {
  const terms = splitFtsTerms(ftsQuery);
  return terms.length > 1 ? terms.join(" OR ") : ftsQuery;
}

function splitFtsTerms(ftsQuery: string): string[] {
  const terms: string[] = [];
  let current = "";
  let quoted = false;
  for (const ch of ftsQuery) {
    if (ch === '"') quoted = !quoted;
    if (!quoted && /\s/.test(ch)) {
      if (current.trim()) terms.push(current.trim());
      current = "";
      continue;
    }
    current += ch;
  }
  if (current.trim()) terms.push(current.trim());
  return terms;
}

function placeholdersFor(values: readonly unknown[]): string {
  return values.map(() => "?").join(", ");
}

function normalizeBm25(rank: number): number {
  const magnitude = Math.abs(rank);
  return magnitude / (1 + magnitude);
}

function scoreRow(row: QueryRow, ftsQuery: string): number {
  const terms = queryTerms(ftsQuery);
  const id = row.id.toLowerCase();
  const slugBoost = terms.some((term) => id.includes(term)) ? 0.05 : 0;
  const namespaceBoost = terms.some((term) => id.startsWith(`load-order.${term}`)) ? 0.01 : 0;
  return Math.min(1, normalizeBm25(row.rank) + slugBoost + namespaceBoost);
}

function queryTerms(ftsQuery: string): string[] {
  return splitFtsTerms(ftsQuery)
    .map((term) => term.replaceAll('"', "").toLowerCase())
    .filter((term) => term.length >= 3);
}

function rowToHit(
  row: QueryRow,
  session: PackSession,
  opts: { score: number; detailLevel: "summary" | "expanded"; includeSources: boolean; includeVariants: boolean; games?: GameCode[] },
): QueryHit {
  const appliesTo = parseJson<{ games?: string[]; engineFamilies?: string[] }>(row.applies_to_json, {});
  const hit: QueryHit = {
    id: row.id,
    packId: session.pack.packId,
    title: row.title,
    score: opts.score,
    appliesTo: {
      games: appliesTo.games ?? [],
      engineFamilies: appliesTo.engineFamilies ?? [],
    },
    synopsis: row.canonical_answer,
    snippet: row.snippet ?? undefined,
    recordRef: { pack: session.pack.packId, path: sourcePathFromId(row.id) },
  };

  if (opts.detailLevel === "expanded") hit.bodyExcerpt = row.body_md.slice(0, 500);
  if (opts.includeSources) hit.sources = parseSources(row.sources_json);
  if (opts.includeVariants) {
    const notes = variantNotes(row.variants_json, opts.games);
    if (notes.length > 0) hit.variantNotes = notes;
  }
  return hit;
}

function parseJson<T>(text: string | null, fallback: T): T {
  if (!text) return fallback;
  try {
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}

function parseSources(text: string): Array<{ kind: string; ref?: string; url?: string }> {
  const raw = parseJson<Array<{ kind?: string; ref?: string; url?: string }>>(text, []);
  return raw
    .filter((source): source is { kind: string; ref?: string; url?: string } => typeof source.kind === "string")
    .map((source) => ({ kind: source.kind, ...(source.ref ? { ref: source.ref } : {}), ...(source.url ? { url: source.url } : {}) }));
}

function variantNotes(variantsText: string | null, games: GameCode[] | undefined): Array<{ game: string; text: string }> {
  const variants = parseJson<Record<string, VariantValue>>(variantsText, {});
  const requestedGames = games && games.length > 0 ? games : (Object.keys(variants) as GameCode[]);
  return requestedGames.flatMap((game) => {
    const variant = variants[game];
    if (!variant) return [];
    const parts = [...(variant.additions ?? []), ...(variant.warnings ?? []).map((warning) => `[${warning.code}|${warning.severity}] ${warning.text}`)];
    const text = parts.join(" ").trim();
    return text.length > 0 ? [{ game, text }] : [];
  });
}

function sourcePathFromId(id: string): string {
  const parts = id.split(".");
  const version = parts.pop();
  if (!version || parts.length === 0) return `records/${id}.md`;
  return `records/${parts.join("/")}.${version}.md`;
}
