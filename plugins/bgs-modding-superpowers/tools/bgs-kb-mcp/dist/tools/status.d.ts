import type { DiscoveryResult } from "../discovery/types.js";
import type { Envelope } from "../envelope/types.js";
import type { SessionRegistry } from "../session/types.js";
export interface StatusToolOptions {
    /** Pack discovery output captured at MCP-server startup. */
    discovery: DiscoveryResult;
    /** Open session registry, used to confirm runtime pack count matches discovery. */
    registry: SessionRegistry;
}
export interface StatusPackData {
    packId: string;
    displayName: string;
    version: string;
    schemaVersion: number;
    minPluginVersion: string;
    root: "bundled" | "cache" | "user";
    rootPath: string;
    recordCount: number;
    domains: string[];
    games: string[];
    integrityOk: boolean;
    loadedAt: string;
}
export interface StatusData {
    packs: StatusPackData[];
    cacheRoot: string;
    userPackRoots: string[];
    totalRecordCount: number;
    schemaVersionSupported: number;
}
export declare function makeStatusTool(opts: StatusToolOptions): (rawArgs: Record<string, unknown>) => Promise<Envelope<StatusData>>;
