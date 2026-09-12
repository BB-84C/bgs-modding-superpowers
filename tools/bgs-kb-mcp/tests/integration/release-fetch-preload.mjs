// Transport-only fixture for a real dist/index.js subprocess. No application
// handlers, discovery roots, session registries or tool wiring are replaced.
import { appendFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.env.BGS_KB_TEST_RELEASE_DIR;
const release = JSON.parse(readFileSync(join(root, 'release.json'), 'utf8'));
const indexBytes = readFileSync(join(root, 'manifest-index.json'));
const index = JSON.parse(indexBytes.toString('utf8'));
const entry = index.packs.find(pack => pack.packId === process.env.BGS_KB_TEST_PACK_ID);
const indexUrl = release.assets.find(asset => asset.name === 'manifest-index.json').browser_download_url;
const asset = release.assets.find(asset => asset.browser_download_url === entry.releaseUrl);
globalThis.fetch = async input => {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  appendFileSync(process.env.BGS_KB_TEST_FETCH_LOG, JSON.stringify({ pid: process.pid, url }) + '\n');
  if (url === 'https://api.github.com/repos/BB-84C/bgs-modding-superpowers/releases/latest') return new Response(JSON.stringify(release));
  if (url === indexUrl) return new Response(indexBytes);
  if (url === entry.releaseUrl) return new Response(readFileSync(join(root, asset.name)));
  throw new Error(`Unexpected outbound request in offline test: ${url}`);
};
