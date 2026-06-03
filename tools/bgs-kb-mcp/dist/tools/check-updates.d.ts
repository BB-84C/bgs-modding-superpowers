import { type Envelope } from "../envelope/types.js";
import type { SessionRegistry } from "../session/types.js";
import { type ReleaseIndex } from "./updates/release-index.js";
export interface CheckUpdateResult {
    packId: string;
    currentVersion: string;
    latestVersion: string;
    upgradeAvailable: boolean;
    breakingChange: boolean;
    releaseUrl: string;
    sha256: string;
    sizeBytes: number;
}
export interface CheckUpdatesData {
    updates: CheckUpdateResult[];
}
export interface CheckUpdatesToolOptions {
    registry: SessionRegistry;
    currentPluginVersion: string;
    releaseIndexFetcher?: () => Promise<ReleaseIndex>;
}
export declare function makeCheckUpdatesTool(opts: CheckUpdatesToolOptions): (rawArgs: Record<string, unknown>) => Promise<Envelope<CheckUpdatesData>>;
