import { createWriteStream } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { createHash } from "node:crypto";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";

export class DownloadFailure extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DownloadFailure";
  }
}

export class IntegrityFailure extends Error {
  constructor(
    public readonly expectedSha256: string,
    public readonly actualSha256: string,
  ) {
    super(`sha256 mismatch: expected ${expectedSha256}, got ${actualSha256}`);
    this.name = "IntegrityFailure";
  }
}

export interface DownloadResult {
  bytesDownloaded: number;
  sha256: string;
}

export async function downloadToFile(args: {
  url: string;
  destPath: string;
  expectedSha256: string;
  expectedSizeBytes?: number;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}): Promise<DownloadResult> {
  const fetchImpl = args.fetchImpl ?? fetch;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), args.timeoutMs ?? 30_000);
  try {
    const response = await fetchImpl(args.url, { signal: controller.signal, headers: { "User-Agent": "bgs-kb-mcp" } });
    if (!response.ok || !response.body) throw new DownloadFailure(`HTTP ${response.status} ${response.statusText}`.trim());
    await mkdir(dirname(args.destPath), { recursive: true });
    const hash = createHash("sha256");
    let bytesDownloaded = 0;
    const meter = new Transform({
      transform(chunk: Buffer, _encoding, callback) {
        bytesDownloaded += chunk.byteLength;
        hash.update(chunk);
        callback(null, chunk);
      },
    });
    await pipeline(Readable.fromWeb(response.body as import("node:stream/web").ReadableStream<Uint8Array>), meter, createWriteStream(args.destPath));
    if (args.expectedSizeBytes !== undefined && bytesDownloaded !== args.expectedSizeBytes) {
      throw new DownloadFailure(`size mismatch: expected ${args.expectedSizeBytes}, got ${bytesDownloaded}`);
    }
    const sha256 = hash.digest("hex");
    if (sha256.toLowerCase() !== args.expectedSha256.toLowerCase()) throw new IntegrityFailure(args.expectedSha256, sha256);
    return { bytesDownloaded, sha256 };
  } catch (error) {
    if (error instanceof IntegrityFailure || error instanceof DownloadFailure) throw error;
    throw new DownloadFailure(error instanceof Error ? error.message : String(error));
  } finally {
    clearTimeout(timeout);
  }
}
