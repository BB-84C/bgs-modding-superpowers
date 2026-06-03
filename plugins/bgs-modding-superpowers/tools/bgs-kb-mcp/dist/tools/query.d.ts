import type { Envelope } from "../envelope/types.js";
import type { SessionRegistry } from "../session/types.js";
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
    appliesTo: {
        games: string[];
        engineFamilies: string[];
    };
    synopsis: string;
    snippet?: string;
    bodyExcerpt?: string;
    variantNotes?: Array<{
        game: string;
        text: string;
    }>;
    sources?: Array<{
        kind: string;
        ref?: string;
        url?: string;
    }>;
    recordRef: {
        pack: string;
        path: string;
    };
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
export declare function makeQueryTool(opts: QueryToolOptions): (rawArgs: Record<string, unknown>) => Promise<Envelope<QueryData>>;
