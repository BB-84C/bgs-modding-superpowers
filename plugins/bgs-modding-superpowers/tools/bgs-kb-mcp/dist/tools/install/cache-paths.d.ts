export interface InstallCachePaths {
    incomingRoot: string;
    packsRoot: string;
    zipPath: string;
    extractPath: string;
    targetPath: string;
}
export declare function resolveInstallCachePaths(cacheRoot: string, packId: string, version: string, tempId?: string): InstallCachePaths;
