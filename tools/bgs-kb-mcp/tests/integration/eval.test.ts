import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

import { discoverPacks } from "../../src/discovery/index.js";
import { openSessions } from "../../src/session/index.js";
import { makeQueryTool } from "../../src/tools/query.js";

const integrationEnabled = process.env.BGS_KB_MCP_INTEGRATION === "1";
const THRESHOLD = 0.8;

interface GoldQuery {
  name: string;
  args: Record<string, unknown>;
  expectedIds: string[];
}

describe.skipIf(!integrationEnabled)("KB-6c retrieval eval", () => {
  test(`current corpus retrieval@3 >= ${THRESHOLD}`, async () => {
    const gold = JSON.parse(await readFile(resolve("tests", "eval", "gold-set.json"), "utf8")) as GoldQuery[];
    const discovery = await discoverPacks();
    const registry = openSessions(discovery.packs);
    const query = makeQueryTool({ registry });
    const failures: string[] = [];
    try {
      for (const item of gold) {
        const result = await query(item.args);
        const hits = result.ok ? result.data.hits.slice(0, 3).map((hit) => hit.id) : [];
        const passed = item.expectedIds.length === 0 ? hits.length === 0 : item.expectedIds.some((id) => hits.includes(id));
        if (!passed) failures.push(`${item.name}: ${hits.join(",")}`);
      }
    } finally {
      registry.closeAll();
    }
    const retrievalAt3 = (gold.length - failures.length) / gold.length;
    expect(retrievalAt3, `failures=${failures.join("; ")}`).toBeGreaterThanOrEqual(THRESHOLD);
  });
});
