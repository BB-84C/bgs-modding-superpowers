import type { LoadedPack } from "../discovery/types.js";
import type { SessionRegistry } from "./types.js";
export declare function openSessions(packs: ReadonlyArray<LoadedPack>): SessionRegistry;
export type { PackSession, SessionRegistry } from "./types.js";
