import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
    setupFiles: ["tests/unit/tracked-temp.setup.ts"],
    testTimeout: 10_000,
  },
});
