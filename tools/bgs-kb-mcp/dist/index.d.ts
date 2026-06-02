import { type Envelope } from "./envelope/types.js";
export declare const TOOL_DEFINITIONS: {
    inputSchema: {
        type: "object";
        additionalProperties: boolean;
    };
    name: string;
    description: string;
}[];
export type ToolHandler = (args: Record<string, unknown>) => Promise<Envelope>;
export interface ServerToolsetOptions {
    status: ToolHandler;
    query: ToolHandler;
    get: ToolHandler;
}
export interface ServerToolset {
    list: () => typeof TOOL_DEFINITIONS;
    invoke: (name: string, args: Record<string, unknown>) => Promise<Envelope>;
}
export declare function jsonResult(body: unknown, isError?: boolean): {
    content: {
        type: "text";
        text: string;
    }[];
    isError: boolean;
};
export declare function buildServerToolset(opts: ServerToolsetOptions): ServerToolset;
export declare function main(): Promise<void>;
