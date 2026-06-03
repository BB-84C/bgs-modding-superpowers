import { type Envelope } from "../envelope/types.js";
import type { SessionRegistry } from "../session/types.js";
import { type ReleaseIndex } from "./updates/release-index.js";
import { extractZip } from "./install/extract.js";
export interface InstallPackData {
    installed: {
        packId: string;
        version: string;
        path: string;
    };
    bytesDownloaded: number;
    sha256Verified: boolean;
    schemaVersionOk: boolean;
    minPluginVersionOk: boolean;
}
export interface InstallPackToolOptions {
    registry: SessionRegistry;
    cacheRoot: string;
    currentPluginVersion: string;
    supportedSchemaVersion: number;
    releaseIndexFetcher?: () => Promise<ReleaseIndex>;
    fetchImpl?: typeof fetch;
    extractZipImpl?: typeof extractZip;
    tempId?: () => string;
}
export declare function makeInstallPackTool(opts: InstallPackToolOptions): (rawArgs: Record<string, unknown>) => Promise<Envelope<InstallPackData>>;
