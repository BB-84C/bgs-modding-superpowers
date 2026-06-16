import type { ToolContext } from "../types.js";
export declare function refreshOrganizer(ctx: ToolContext, opts?: {
    saveChanges?: boolean;
}): Promise<void>;
export declare function invalidateWorld(ctx: ToolContext, profiles?: string[]): Promise<void>;
export declare function refreshOrganizerAndInvalidateWorld(ctx: ToolContext, profiles?: string[], opts?: {
    saveChanges?: boolean;
}): Promise<void>;
