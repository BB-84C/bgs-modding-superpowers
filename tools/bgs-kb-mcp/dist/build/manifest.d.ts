import type { PackManifest, PackMeta, SourceRecord } from "./types.js";
export declare function readPackMeta(packRoot: string): Promise<PackMeta>;
export declare function sha256File(path: string): Promise<string>;
export declare function readSourceCommit(packRoot: string): Promise<string | undefined>;
export declare function buildManifest(args: {
    packRoot: string;
    records: SourceRecord[];
    meta: PackMeta;
    builtAt: string;
    sha256: string;
}): Promise<PackManifest>;
export declare function writeManifest(packRoot: string, manifest: PackManifest): Promise<string>;
