import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { afterEach, expect, test } from "vitest";

import { buildPack } from "../../src/build/index.js";
import type { LoadedPack, PackRoot } from "../../src/discovery/types.js";
import { openSessions } from "../../src/session/index.js";
import { cleanupTempPacks, makeTempPack, writeFixturePack, writeRecord, recordFrontmatter } from "./test-helpers.js";

afterEach(cleanupTempPacks);

const loadedAt = "2026-06-02T00:00:00.000Z";

async function buildLoadedPack(
  packId: string,
  records: Array<{ path: string; id: string; title?: string; domains?: string[]; games?: string[]; queryKeys?: string[] }>,
  root: PackRoot = "bundled",
): Promise<LoadedPack> {
  const packRoot = await makeTempPack(`kb-session-${packId}-`);
  await writeFile(
    join(packRoot, "bgs-kb-meta.yml"),
    `packId: ${packId}\ndisplayName: ${packId} display\nversion: 2026.06.02\nschemaVersion: 1\nminPluginVersion: 0.2.0\nowner: tests\nlicense: MIT\n`,
    "utf8",
  );
  await writeFixturePack(packRoot, records);
  const built = await buildPack(packRoot);
  return {
    packId: built.manifest.packId,
    displayName: built.manifest.displayName,
    version: built.manifest.version,
    schemaVersion: built.manifest.schemaVersion,
    minPluginVersion: built.manifest.minPluginVersion,
    root,
    rootPath: packRoot,
    packRoot,
    kbSqlitePath: built.kbSqlitePath,
    manifestPath: built.manifestPath,
    manifest: built.manifest,
    integrityOk: true,
    loadedAt,
  };
}

async function buildTwoRecordPack(packId = "session-pack"): Promise<LoadedPack> {
  return buildLoadedPack(packId, [
    { path: "xedit/archive-precedence.v1.md", id: "xedit.archive-precedence.v1", title: "Archive precedence", queryKeys: ["archives"] },
    { path: "xedit/plugins-query.v1.md", id: "xedit.plugins-query.v1", title: "Plugins query", queryKeys: ["plugins", "load order"] },
  ]);
}

test("opens a read-only pack session and reads rows", async () => {
  const pack = await buildTwoRecordPack();
  const registry = openSessions([pack]);
  try {
    const rows = registry.all()[0].all<{ id: string; title: string }>("SELECT id, title FROM records ORDER BY id");

    expect(rows).toEqual([
      { id: "xedit.archive-precedence.v1", title: "Archive precedence" },
      { id: "xedit.plugins-query.v1", title: "Plugins query" },
    ]);
  } finally {
    registry.closeAll();
  }
});

test("runs a parameterized FTS5 query", async () => {
  const pack = await buildTwoRecordPack();
  const registry = openSessions([pack]);
  try {
    const rows = registry.all()[0].all<{ id: string }>(
      "SELECT records.id FROM records JOIN records_fts ON records.rowid = records_fts.rowid WHERE records_fts MATCH ? ORDER BY rank LIMIT 5",
      ["plugins"],
    );

    expect(rows).toEqual([{ id: "xedit.plugins-query.v1" }]);
  } finally {
    registry.closeAll();
  }
});

test("caches prepared statements for repeated SQL shapes", async () => {
  const pack = await buildTwoRecordPack();
  const registry = openSessions([pack]);
  try {
    const session = registry.all()[0];
    const sql = "SELECT id FROM records WHERE id = ?";

    expect(session.get(sql, ["xedit.archive-precedence.v1"])).toEqual({ id: "xedit.archive-precedence.v1" });
    expect(session.get(sql, ["xedit.plugins-query.v1"])).toEqual({ id: "xedit.plugins-query.v1" });

    // The cache is a runtime optimization, not public API. This narrow readback
    // verifies the required cache without adding a production test hook.
    expect((session as unknown as { prepared: Map<string, unknown> }).prepared.size).toBe(1);
  } finally {
    registry.closeAll();
  }
});

test("get returns null for empty results", async () => {
  const pack = await buildTwoRecordPack();
  const registry = openSessions([pack]);
  try {
    expect(registry.all()[0].get("SELECT id FROM records WHERE id = ?", ["missing.v1"])).toBeNull();
  } finally {
    registry.closeAll();
  }
});

test("read-only sessions reject mutation attempts", async () => {
  const pack = await buildTwoRecordPack();
  const registry = openSessions([pack]);
  try {
    // On Node 22's node:sqlite this surfaces as a SQLite read-only error; the
    // exact code/message is captured in the KB-2b closeout for later tool mapping.
    expect(() => registry.all()[0].all("UPDATE records SET title = title WHERE id = ?", ["xedit.plugins-query.v1"])).toThrow(/readonly|read-only|SQLITE_READONLY/i);
  } finally {
    registry.closeAll();
  }
});

test("close is idempotent and later queries fail clearly", async () => {
  const pack = await buildTwoRecordPack();
  const session = openSessions([pack]).all()[0];

  expect(() => session.close()).not.toThrow();
  expect(() => session.close()).not.toThrow();
  expect(() => session.close()).not.toThrow();
  expect(() => session.all("SELECT id FROM records")).toThrow(/PackSession for session-pack is closed/);
});

test("closeAll continues after one session close throws", async () => {
  const first = await buildLoadedPack("bad-close-pack", [{ path: "a.v1.md", id: "a.v1" }]);
  const second = await buildLoadedPack("good-close-pack", [{ path: "b.v1.md", id: "b.v1" }]);
  const registry = openSessions([first, second]);
  const [bad, good] = registry.all();
  const originalBadClose = bad.close.bind(bad);
  bad.close = () => {
    originalBadClose();
    throw new Error("simulated close failure");
  };

  expect(() => registry.closeAll()).not.toThrow();
  expect(() => good.all("SELECT id FROM records")).toThrow(/PackSession for good-close-pack is closed/);
});

test("byPackId returns a loaded session or null", async () => {
  const present = await buildLoadedPack("present", [{ path: "present.v1.md", id: "present.v1" }]);
  const other = await buildLoadedPack("other", [{ path: "other.v1.md", id: "other.v1" }]);
  const registry = openSessions([present, other]);
  try {
    expect(registry.byPackId("present")?.pack.packId).toBe("present");
    expect(registry.byPackId("absent")).toBeNull();
  } finally {
    registry.closeAll();
  }
});

test("all returns sessions in discovery-priority input order", async () => {
  const bundled = await buildLoadedPack("bundled-pack", [{ path: "a.v1.md", id: "a.v1" }], "bundled");
  const cache = await buildLoadedPack("cache-pack", [{ path: "b.v1.md", id: "b.v1" }], "cache");
  const user = await buildLoadedPack("user-pack", [{ path: "c.v1.md", id: "c.v1" }], "user");
  const registry = openSessions([bundled, cache, user]);
  try {
    expect(registry.all().map((session) => `${session.pack.root}:${session.pack.packId}`)).toEqual(["bundled:bundled-pack", "cache:cache-pack", "user:user-pack"]);
  } finally {
    registry.closeAll();
  }
});

test("parameter binding treats injection text as a literal", async () => {
  const packRoot = await makeTempPack("kb-session-injection-");
  await writeFile(
    join(packRoot, "bgs-kb-meta.yml"),
    "packId: injection-pack\ndisplayName: Injection Pack\nversion: 2026.06.02\nschemaVersion: 1\nminPluginVersion: 0.2.0\nowner: tests\nlicense: MIT\n",
    "utf8",
  );
  await writeRecord(packRoot, "safe-id.v1.md", recordFrontmatter({ id: "safe-id.v1", title: "Safe ID" }));
  const built = await buildPack(packRoot);
  const pack: LoadedPack = {
    packId: built.manifest.packId,
    displayName: built.manifest.displayName,
    version: built.manifest.version,
    schemaVersion: built.manifest.schemaVersion,
    minPluginVersion: built.manifest.minPluginVersion,
    root: "bundled",
    rootPath: packRoot,
    packRoot,
    kbSqlitePath: built.kbSqlitePath,
    manifestPath: built.manifestPath,
    manifest: built.manifest,
    integrityOk: true,
    loadedAt,
  };
  const registry = openSessions([pack]);
  try {
    const rows = registry.all()[0].all("SELECT * FROM records WHERE id = ?", ["safe-id.v1' OR '1'='1"]);

    expect(rows).toEqual([]);
  } finally {
    registry.closeAll();
  }
});
