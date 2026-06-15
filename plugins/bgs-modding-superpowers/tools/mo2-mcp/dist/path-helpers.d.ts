import type { ToolContext } from "./types.js";
export declare function resolveModMetaPath(modName: string, ctx: ToolContext): Promise<string>;
export declare function resolveModsDir(ctx: ToolContext): Promise<string>;
export declare function resolveProfileDir(ctx: ToolContext, profile?: string): string;
