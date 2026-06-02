import { performance } from "node:perf_hooks";
import { z } from "zod";
import { ok, refuse } from "../envelope/index.js";
import { KB_ERROR_CODES } from "../envelope/types.js";
import { DomainEnum, GameCodeEnum } from "../types/enums.js";
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
export function makeQueryTool(opts) {
    return async (rawArgs) => {
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
        const candidates = [];
        for (const session of sessions) {
            let rows = querySession(session, sanitizedQuery, {
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
                },
                // Cursor support is intentionally stubbed in v1. Agents should refine
                // queries rather than page broad searches until KB-6 adds real cursors.
                nextCursor: null,
            },
            status: "completed",
        });
    };
}
function querySession(session, ftsQuery, opts) {
    const clauses = ["records_fts MATCH ?"];
    const params = [ftsQuery];
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
    return session.all(`SELECT records.id, records.title, records.canonical_answer, records.body_md,
       records.applies_to_json, records.variants_json, records.sources_json,
       records.pack_id,
       snippet(records_fts, 1, '[', ']', '…', 16) AS snippet,
       bm25(records_fts, 6.0, 1.0, 8.0, 2.0) AS rank
     FROM records
     JOIN records_fts ON records.rowid = records_fts.rowid
     WHERE ${clauses.join(" AND ")}
     ORDER BY rank
     LIMIT ?`, params);
}
function orFallbackQuery(ftsQuery) {
    const terms = splitFtsTerms(ftsQuery);
    return terms.length > 1 ? terms.join(" OR ") : ftsQuery;
}
function splitFtsTerms(ftsQuery) {
    const terms = [];
    let current = "";
    let quoted = false;
    for (const ch of ftsQuery) {
        if (ch === '"')
            quoted = !quoted;
        if (!quoted && /\s/.test(ch)) {
            if (current.trim())
                terms.push(current.trim());
            current = "";
            continue;
        }
        current += ch;
    }
    if (current.trim())
        terms.push(current.trim());
    return terms;
}
function placeholdersFor(values) {
    return values.map(() => "?").join(", ");
}
function normalizeBm25(rank) {
    const magnitude = Math.abs(rank);
    return magnitude / (1 + magnitude);
}
function scoreRow(row, ftsQuery) {
    const terms = queryTerms(ftsQuery);
    const id = row.id.toLowerCase();
    const slugBoost = terms.some((term) => id.includes(term)) ? 0.05 : 0;
    const namespaceBoost = terms.some((term) => id.startsWith(`load-order.${term}`)) ? 0.01 : 0;
    return Math.min(1, normalizeBm25(row.rank) + slugBoost + namespaceBoost);
}
function queryTerms(ftsQuery) {
    return splitFtsTerms(ftsQuery)
        .map((term) => term.replaceAll('"', "").toLowerCase())
        .filter((term) => term.length >= 3);
}
function rowToHit(row, session, opts) {
    const appliesTo = parseJson(row.applies_to_json, {});
    const hit = {
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
    if (opts.detailLevel === "expanded")
        hit.bodyExcerpt = row.body_md.slice(0, 500);
    if (opts.includeSources)
        hit.sources = parseSources(row.sources_json);
    if (opts.includeVariants) {
        const notes = variantNotes(row.variants_json, opts.games);
        if (notes.length > 0)
            hit.variantNotes = notes;
    }
    return hit;
}
function parseJson(text, fallback) {
    if (!text)
        return fallback;
    try {
        return JSON.parse(text);
    }
    catch {
        return fallback;
    }
}
function parseSources(text) {
    const raw = parseJson(text, []);
    return raw
        .filter((source) => typeof source.kind === "string")
        .map((source) => ({ kind: source.kind, ...(source.ref ? { ref: source.ref } : {}), ...(source.url ? { url: source.url } : {}) }));
}
function variantNotes(variantsText, games) {
    const variants = parseJson(variantsText, {});
    const requestedGames = games && games.length > 0 ? games : Object.keys(variants);
    return requestedGames.flatMap((game) => {
        const variant = variants[game];
        if (!variant)
            return [];
        const parts = [...(variant.additions ?? []), ...(variant.warnings ?? []).map((warning) => `[${warning.code}|${warning.severity}] ${warning.text}`)];
        const text = parts.join(" ").trim();
        return text.length > 0 ? [{ game, text }] : [];
    });
}
function sourcePathFromId(id) {
    const parts = id.split(".");
    const version = parts.pop();
    if (!version || parts.length === 0)
        return `records/${id}.md`;
    return `records/${parts.join("/")}.${version}.md`;
}
//# sourceMappingURL=query.js.map