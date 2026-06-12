import type { DiscoveryResult } from "./discovery/types.js";
export interface DevStatusOptions {
    json?: boolean;
    pack?: string;
    includeUserpacks?: boolean;
}
export interface FormatDevStatusOptions extends DevStatusOptions {
    context?: string;
}
export declare function formatDevStatus(discovery: DiscoveryResult, opts?: FormatDevStatusOptions): string;
export declare function runDevStatus(opts?: DevStatusOptions): Promise<string>;
