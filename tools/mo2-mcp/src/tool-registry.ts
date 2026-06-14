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

const _registry = new Map<string, ToolDef>();

export function registerTool(def: ToolDef): void {
  _registry.set(def.name, def);
}

export function getTool(name: string): ToolDef | undefined {
  return _registry.get(name);
}

export function getAllTools(): ToolDef[] {
  return [..._registry.values()];
}

/** Test-only reset. */
export function _clearToolsForTests(): void {
  _registry.clear();
}
