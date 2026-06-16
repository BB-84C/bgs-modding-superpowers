import { beforeAll, describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import {
  ARTIFACTS,
  HARNESS_MO2_ROOT,
  HARNESS_PROFILE,
  expectOk,
  harnessEnv,
  planApply,
  stripCustomExecutables,
  uniqueName,
  withMcp,
  writeEvidence,
} from "./acceptance-shared.js";

describe.skipIf(process.env.MO2_MCP_ACCEPTANCE !== "1")("v1 acceptance (closed)", () => {
  beforeAll(async () => {
    await mkdir(ARTIFACTS, { recursive: true });
  });

  it("AT8: customExecutables add/edit/remove preserves non-executable INI sections", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const iniPath = join(HARNESS_MO2_ROOT, "ModOrganizer.ini");
      const before = await readFile(iniPath, "utf8");
      const title = uniqueName("AT8 Tool");
      const add = await planApply(mcp, "mo2_configure_executable", {
        action: "add",
        entry: { title, binary: "C:/Windows/System32/cmd.exe", arguments: "/c ver", workingDirectory: "C:/Windows/System32" },
      });
      const listedAfterAdd = await mcp.call("mo2_list_executables", {});
      const edit = await planApply(mcp, "mo2_configure_executable", {
        action: "edit",
        title,
        updates: { arguments: "/c echo edited" },
      });
      const remove = await planApply(mcp, "mo2_configure_executable", { action: "remove", title });
      const after = await readFile(iniPath, "utf8");
      expectOk(add.apply);
      expectOk(edit.apply);
      expectOk(remove.apply);
      expectOk(listedAfterAdd);
      expect(stripCustomExecutables(after)).toBe(stripCustomExecutables(before));
      await writeEvidence("AT8-custom-executables-roundtrip", { add, listedAfterAdd, edit, remove });
    });
  }, 120_000);

  it("AT9: profile create, clone, rename, and filesystem cleanup", async () => {
    await withMcp(harnessEnv(), async (mcp) => {
      const created = uniqueName("AT9-Created");
      const cloned = uniqueName("AT9-Cloned");
      const renamed = uniqueName("AT9-Renamed");
      try {
        const create = await planApply(mcp, "mo2_create_profile", { name: created });
        const clone = await planApply(mcp, "mo2_clone_profile", { source: HARNESS_PROFILE, target: cloned });
        const renameProfile = await planApply(mcp, "mo2_rename_profile", { old_name: cloned, new_name: renamed });
        expectOk(create.apply);
        expectOk(clone.apply);
        expectOk(renameProfile.apply);
        expect(existsSync(join(HARNESS_MO2_ROOT, "profiles", renamed))).toBe(true);
        await writeEvidence("AT9-profile-lifecycle", { create, clone, renameProfile });
      } finally {
        await rm(join(HARNESS_MO2_ROOT, "profiles", created), { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "profiles", cloned), { recursive: true, force: true });
        await rm(join(HARNESS_MO2_ROOT, "profiles", renamed), { recursive: true, force: true });
      }
    });
  }, 120_000);
});
