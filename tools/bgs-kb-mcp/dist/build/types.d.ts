export interface SourceRecord {
    sourcePath: string;
    id: string;
    title: string;
    domains: string[];
    appliesTo: {
        games: string[];
        engineFamilies?: string[];
        excludes?: string[];
    };
    canonical: {
        answer: string;
        confidence: string;
    };
    variants?: Record<string, {
        additions?: string[];
        warnings?: {
            code: string;
            severity: string;
            text: string;
        }[];
        deletions?: string[];
    }>;
    queryKeys?: string[];
    severity?: string;
    sources: {
        kind: string;
        ref?: string;
        url?: string;
        sectionPath?: string;
    }[];
    related?: string[];
    seeAlso?: string[];
    lastReviewed: string;
    schemaVersion: number;
    bodyMd: string;
}
export interface PackManifest {
    packId: string;
    displayName: string;
    version: string;
    schemaVersion: number;
    minPluginVersion: string;
    owner: string;
    license: string;
    sourceCommit?: string;
    builtAt: string;
    recordCount: number;
    domains: string[];
    games: string[];
    engineFamilies: string[];
    sha256: {
        "kb.sqlite": string;
    };
}
export interface PackMeta {
    packId: string;
    displayName: string;
    version: string;
    schemaVersion: number;
    minPluginVersion: string;
    owner: string;
    license: string;
}
