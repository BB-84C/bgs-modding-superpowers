import { z } from "zod";

export const GAME_CODE_VALUES = ["SkyrimLE", "SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"] as const;

export const DOMAIN_VALUES = [
  "xedit",
  "plugin-format",
  "load-order",
  "archive-precedence",
  "papyrus",
  "engine",
  "tooling.spriggit",
  "tooling.mutagen",
  "tooling.loot",
  "save-file",
  "debugging",
  "game-specific.vr",
  "version-differences",
  "file-conflicts",
  "install-planning",
] as const;

export const GameCodeEnum = z.enum(GAME_CODE_VALUES);
export const DomainEnum = z.enum(DOMAIN_VALUES);

export type GameCode = z.infer<typeof GameCodeEnum>;
export type Domain = z.infer<typeof DomainEnum>;
