/**
 * Tool registry — handlers register here via side-effect imports.
 * Bootstrap reads getAllTools() to populate the MCP server's tools/list.
 */
import { z } from "zod";
import type { ToolContext } from "./types.js";
export interface ToolDef {
    name: string;
    description: string;
    inputSchema: z.ZodTypeAny;
    handler: (args: Record<string, unknown>, ctx: ToolContext) => Promise<unknown>;
    tier: "T1" | "T2" | "T3";
}
export declare function registerTool(def: ToolDef): void;
export declare function getTool(name: string): ToolDef | undefined;
export declare function getAllTools(): ToolDef[];
/** Test-only reset. */
export declare function _clearToolsForTests(): void;
