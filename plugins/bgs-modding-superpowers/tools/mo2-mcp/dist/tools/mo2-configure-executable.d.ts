import { type MoIniCustomExecutable } from "../mo-ini.js";
export declare function _serializeValue(key: string, value: string | boolean): string;
export declare function _rewriteCustomExecutables(raw: string, range: [number, number] | undefined, entries: MoIniCustomExecutable[]): string;
