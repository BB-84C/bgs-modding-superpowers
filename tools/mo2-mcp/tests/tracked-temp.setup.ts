import { afterEach } from "vitest";
import { cleanupTrackedTempDirs, createTrackedTempDir, createTrackedTempDirSync } from "./tracked-temp.js";

globalThis.createTrackedTempDir = createTrackedTempDir;
globalThis.createTrackedTempDirSync = createTrackedTempDirSync;
afterEach(async () => {
  await cleanupTrackedTempDirs();
});
