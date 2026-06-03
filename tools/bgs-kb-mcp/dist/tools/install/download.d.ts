export declare class DownloadFailure extends Error {
    constructor(message: string);
}
export declare class IntegrityFailure extends Error {
    readonly expectedSha256: string;
    readonly actualSha256: string;
    constructor(expectedSha256: string, actualSha256: string);
}
export interface DownloadResult {
    bytesDownloaded: number;
    sha256: string;
}
export declare function downloadToFile(args: {
    url: string;
    destPath: string;
    expectedSha256: string;
    expectedSizeBytes?: number;
    fetchImpl?: typeof fetch;
    timeoutMs?: number;
}): Promise<DownloadResult>;
