import { z } from "zod";
export const DEFAULT_LATEST_RELEASE_API_URL = "https://api.github.com/repos/BB-84C/bgs-modding-superpowers/releases/latest";
export const DEFAULT_RELEASE_DOWNLOAD_BASE = "https://github.com/BB-84C/bgs-modding-superpowers/releases/download";
// manifest-index.json shape:
// {
//   "releaseTag": "kb-2026.06.02",
//   "publishedAt": "2026-06-02T00:00:00Z",
//   "packs": [{
//     "packId": "bgs-kb-core",
//     "version": "2026.06.02",
//     "schemaVersion": 1,
//     "minPluginVersion": "0.2.0",
//     "releaseUrl": "https://github.com/.../bgs-kb-core-2026.06.02.zip",
//     "sha256": "<64-hex>",
//     "sizeBytes": 123456
//   }]
// }
const PackEntrySchema = z
    .object({
    packId: z.string().min(1),
    version: z.string().min(1),
    schemaVersion: z.number().int().min(1),
    minPluginVersion: z.string().min(1),
    releaseUrl: z.string().url(),
    sha256: z.string().regex(/^[a-fA-F0-9]{64}$/),
    sizeBytes: z.number().int().nonnegative(),
})
    .strict();
const ReleaseIndexSchema = z
    .object({
    releaseTag: z.string().min(1),
    publishedAt: z.string().min(1),
    packs: z.array(PackEntrySchema),
})
    .strict();
const GitHubLatestReleaseSchema = z
    .object({
    tag_name: z.string().min(1),
    assets: z.array(z.object({ name: z.string(), browser_download_url: z.string().url().optional() }).passthrough()).optional(),
})
    .passthrough();
async function fetchJson(url, opts) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), opts.timeoutMs);
    try {
        const response = await opts.fetchImpl(url, { signal: controller.signal, headers: { "User-Agent": "bgs-kb-mcp" } });
        if (!response.ok)
            throw new Error(`HTTP ${response.status} ${response.statusText}`.trim());
        return await response.json();
    }
    finally {
        clearTimeout(timeout);
    }
}
export async function fetchReleaseIndex(options = {}) {
    const fetchImpl = options.fetchImpl ?? fetch;
    const timeoutMs = options.timeoutMs ?? 30_000;
    let manifestIndexUrl = options.manifestIndexUrl;
    if (!manifestIndexUrl) {
        const latestRaw = await fetchJson(options.latestReleaseApiUrl ?? DEFAULT_LATEST_RELEASE_API_URL, { fetchImpl, timeoutMs });
        const latest = GitHubLatestReleaseSchema.parse(latestRaw);
        manifestIndexUrl =
            latest.assets?.find((asset) => asset.name === "manifest-index.json")?.browser_download_url ??
                `${DEFAULT_RELEASE_DOWNLOAD_BASE}/${encodeURIComponent(latest.tag_name)}/manifest-index.json`;
    }
    const rawIndex = await fetchJson(manifestIndexUrl, { fetchImpl, timeoutMs });
    return ReleaseIndexSchema.parse(rawIndex);
}
//# sourceMappingURL=release-index.js.map