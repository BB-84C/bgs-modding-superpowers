import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { discoverPacks } from "../../dist/discovery/index.js";
import { openSessions } from "../../dist/session/index.js";
import { makeQueryTool } from "../../dist/tools/query.js";

const here = dirname(fileURLToPath(import.meta.url));
const gold = JSON.parse(await readFile(resolve(here, "gold-set.json"), "utf8"));

const discovery = await discoverPacks();
const registry = openSessions(discovery.packs);
const query = makeQueryTool({ registry });

const failures = [];
try {
  for (const item of gold) {
    const result = await query(item.args);
    const hits = result.ok ? result.data.hits.slice(0, 3).map((hit) => hit.id) : [];
    const expected = item.expectedIds ?? [];
    const passed = expected.length === 0 ? hits.length === 0 : expected.some((id) => hits.includes(id));
    if (!passed) failures.push(item.name);
    console.log(`${passed ? "PASS" : "FAIL"}\t${item.name}\texpected=${expected.join("|") || "<no hits>"}\ttop3=${hits.join(",") || "<none>"}`);
  }
} finally {
  registry.closeAll();
}

const passedCount = gold.length - failures.length;
const retrievalAt3 = passedCount / gold.length;
console.log(`retrieval@3=${retrievalAt3.toFixed(3)} passed=${passedCount}/${gold.length} failures=${failures.join(",")}`);
if (retrievalAt3 < 0.8) process.exit(1);
