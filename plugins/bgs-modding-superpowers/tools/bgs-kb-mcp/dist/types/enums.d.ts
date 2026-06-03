import { z } from "zod";
export declare const GAME_CODE_VALUES: readonly ["SkyrimLE", "SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"];
export declare const DOMAIN_VALUES: readonly ["xedit", "plugin-format", "load-order", "archive-precedence", "papyrus", "engine", "tooling.spriggit", "tooling.mutagen", "tooling.loot", "save-file", "debugging", "game-specific.vr", "version-differences", "file-conflicts", "install-planning"];
export declare const GameCodeEnum: z.ZodEnum<["SkyrimLE", "SkyrimSE", "SkyrimAE", "SkyrimVR", "Fallout4", "Fallout4VR", "Fallout3", "FalloutNV", "Starfield"]>;
export declare const DomainEnum: z.ZodEnum<["xedit", "plugin-format", "load-order", "archive-precedence", "papyrus", "engine", "tooling.spriggit", "tooling.mutagen", "tooling.loot", "save-file", "debugging", "game-specific.vr", "version-differences", "file-conflicts", "install-planning"]>;
export type GameCode = z.infer<typeof GameCodeEnum>;
export type Domain = z.infer<typeof DomainEnum>;
