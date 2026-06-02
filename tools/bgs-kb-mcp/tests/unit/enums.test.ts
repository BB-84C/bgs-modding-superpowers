import { expect, test } from "vitest";

import { DOMAIN_VALUES, GAME_CODE_VALUES, DomainEnum, GameCodeEnum } from "../../src/types/enums.js";

test("game code enum mirrors the record schema values", () => {
  expect(GAME_CODE_VALUES).toEqual(["SkyrimLE", "SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"]);
  expect(GameCodeEnum.parse("Fallout4")).toBe("Fallout4");
});

test("domain enum mirrors the record schema values", () => {
  expect(DOMAIN_VALUES).toContain("xedit");
  expect(DOMAIN_VALUES).toContain("install-planning");
  expect(DomainEnum.parse("load-order")).toBe("load-order");
});
