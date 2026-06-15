import type { Rule, ToolContext } from "./types.js";
export interface DispatchToolCallInput {
    toolName: string;
    rawArgs: unknown;
    ctx: ToolContext;
    rules: Rule[];
}
export interface DispatchToolCallResult {
    content: Array<{
        type: "text";
        text: string;
    }>;
    isError?: boolean;
}
export declare function dispatchToolCall({ toolName, rawArgs, ctx, rules, }: DispatchToolCallInput): Promise<DispatchToolCallResult>;
