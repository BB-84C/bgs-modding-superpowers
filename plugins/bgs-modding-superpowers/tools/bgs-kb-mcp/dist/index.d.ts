import { type Envelope } from "./envelope/types.js";
export declare const TOOL_DEFINITIONS: ({
    name: string;
    description: string;
    inputSchema: {
        type: "object";
        properties: {
            query?: undefined;
            games?: undefined;
            domains?: undefined;
            toolchains?: undefined;
            kinds?: undefined;
            packIds?: undefined;
            maxResults?: undefined;
            detailLevel?: undefined;
            includeVariants?: undefined;
            includeSources?: undefined;
            cursor?: undefined;
            id?: undefined;
            game?: undefined;
            packId?: undefined;
            version?: undefined;
            dryRun?: undefined;
        };
        additionalProperties: false;
        required?: undefined;
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: "object";
        properties: {
            query: {
                type: string;
                description: string;
            };
            games: {
                type: string;
                items: {
                    type: string;
                    enum: ("SkyrimLE" | "SkyrimSE" | "SkyrimAE" | "SkyrimVR" | "Fallout4" | "Fallout4VR" | "Fallout3" | "FalloutNV" | "Starfield")[];
                };
                description: string;
            };
            domains: {
                type: string;
                items: {
                    type: string;
                    enum: ("xedit" | "plugin-format" | "load-order" | "archive-precedence" | "papyrus" | "engine" | "tooling.spriggit" | "tooling.mutagen" | "tooling.loot" | "save-file" | "debugging" | "game-specific.vr" | "version-differences" | "file-conflicts" | "install-planning")[];
                };
                description: string;
            };
            toolchains: {
                type: string;
                items: {
                    type: string;
                };
                description: string;
            };
            kinds: {
                type: string;
                items: {
                    type: string;
                    enum: ("rule" | "workflow" | "gotcha" | "explanation" | "source-map")[];
                };
                description: string;
            };
            packIds: {
                type: string;
                items: {
                    type: string;
                };
                description: string;
            };
            maxResults: {
                type: string;
                minimum: number;
                description: string;
            };
            detailLevel: {
                type: string;
                enum: ("summary" | "expanded")[];
                description: string;
            };
            includeVariants: {
                type: string;
                description: string;
            };
            includeSources: {
                type: string;
                description: string;
            };
            cursor: {
                type: string;
                description: string;
            };
            id?: undefined;
            game?: undefined;
            packId?: undefined;
            version?: undefined;
            dryRun?: undefined;
        };
        required: string[];
        additionalProperties: false;
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: "object";
        properties: {
            id: {
                type: string;
                minLength: number;
                description: string;
            };
            game: {
                type: string;
                enum: ("SkyrimLE" | "SkyrimSE" | "SkyrimAE" | "SkyrimVR" | "Fallout4" | "Fallout4VR" | "Fallout3" | "FalloutNV" | "Starfield")[];
                description: string;
            };
            packId: {
                type: string;
                minLength: number;
                description: string;
            };
            query?: undefined;
            games?: undefined;
            domains?: undefined;
            toolchains?: undefined;
            kinds?: undefined;
            packIds?: undefined;
            maxResults?: undefined;
            detailLevel?: undefined;
            includeVariants?: undefined;
            includeSources?: undefined;
            cursor?: undefined;
            version?: undefined;
            dryRun?: undefined;
        };
        required: string[];
        additionalProperties: false;
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: "object";
        properties: {
            packId: {
                type: string;
                minLength: number;
                description: string;
            };
            version: {
                type: string;
                minLength: number;
                description: string;
            };
            dryRun: {
                type: string;
                description: string;
            };
            query?: undefined;
            games?: undefined;
            domains?: undefined;
            toolchains?: undefined;
            kinds?: undefined;
            packIds?: undefined;
            maxResults?: undefined;
            detailLevel?: undefined;
            includeVariants?: undefined;
            includeSources?: undefined;
            cursor?: undefined;
            id?: undefined;
            game?: undefined;
        };
        required: string[];
        additionalProperties: false;
    };
})[];
export type ToolHandler = (args: Record<string, unknown>) => Promise<Envelope>;
export interface ServerToolsetOptions {
    status: ToolHandler;
    query: ToolHandler;
    get: ToolHandler;
    checkUpdates: ToolHandler;
    installPack: ToolHandler;
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
