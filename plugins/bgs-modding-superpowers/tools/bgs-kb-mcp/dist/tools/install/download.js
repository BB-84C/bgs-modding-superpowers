import { createWriteStream } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { createHash } from "node:crypto";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
export class DownloadFailure extends Error {
    constructor(message) {
        super(message);
        this.name = "DownloadFailure";
    }
}
export class IntegrityFailure extends Error {
    expectedSha256;
    actualSha256;
    constructor(expectedSha256, actualSha256) {
        super(`sha256 mismatch: expected ${expectedSha256}, got ${actualSha256}`);
        this.expectedSha256 = expectedSha256;
        this.actualSha256 = actualSha256;
        this.name = "IntegrityFailure";
    }
}
export async function downloadToFile(args) {
    const fetchImpl = args.fetchImpl ?? fetch;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), args.timeoutMs ?? 30_000);
    try {
        const response = await fetchImpl(args.url, { signal: controller.signal, headers: { "User-Agent": "bgs-kb-mcp" } });
        if (!response.ok || !response.body)
            throw new DownloadFailure(`HTTP ${response.status} ${response.statusText}`.trim());
        await mkdir(dirname(args.destPath), { recursive: true });
        const hash = createHash("sha256");
        let bytesDownloaded = 0;
        const meter = new Transform({
            transform(chunk, _encoding, callback) {
                bytesDownloaded += chunk.byteLength;
                hash.update(chunk);
                callback(null, chunk);
            },
        });
        await pipeline(Readable.fromWeb(response.body), meter, createWriteStream(args.destPath));
        if (args.expectedSizeBytes !== undefined && bytesDownloaded !== args.expectedSizeBytes) {
            throw new DownloadFailure(`size mismatch: expected ${args.expectedSizeBytes}, got ${bytesDownloaded}`);
        }
        const sha256 = hash.digest("hex");
        if (sha256.toLowerCase() !== args.expectedSha256.toLowerCase())
            throw new IntegrityFailure(args.expectedSha256, sha256);
        return { bytesDownloaded, sha256 };
    }
    catch (error) {
        if (error instanceof IntegrityFailure || error instanceof DownloadFailure)
            throw error;
        throw new DownloadFailure(error instanceof Error ? error.message : String(error));
    }
    finally {
        clearTimeout(timeout);
    }
}
//# sourceMappingURL=download.js.map