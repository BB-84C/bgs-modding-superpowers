import type { CollisionReport, DiscoveryOptions, DiscoveryResult, LoadedPack, PackCandidate } from "./types.js";
interface LoadedCandidate extends LoadedPack {
}
export declare function selectWinner(candidates: PackCandidate[]): {
    winner: PackCandidate;
    losers: PackCandidate[];
};
export declare function applyPrecedence(candidates: LoadedCandidate[]): {
    packs: LoadedPack[];
    collisions: CollisionReport[];
};
export declare function discoverPacks(opts?: DiscoveryOptions): Promise<DiscoveryResult>;
export {};
