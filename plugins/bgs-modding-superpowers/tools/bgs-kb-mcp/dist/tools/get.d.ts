import type { Envelope } from "../envelope/types.js";
import type { SessionRegistry } from "../session/types.js";
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
export declare function makeGetTool(opts: GetToolOptions): (rawArgs: Record<string, unknown>) => Promise<Envelope<GetData>>;
