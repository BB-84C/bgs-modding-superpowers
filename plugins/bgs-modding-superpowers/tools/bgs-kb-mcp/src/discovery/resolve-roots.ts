import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export function resolvePluginRoot(moduleUrl: string): string {
  return resolve(dirname(fileURLToPath(moduleUrl)), "..", "..", "..", "..");
}

export function defaultCacheRoot(): string {
  if (process.platform === "win32" && process.env.LOCALAPPDATA) {
    return resolve(process.env.LOCALAPPDATA, "bgs-modding-superpowers", "kb", "packs");
  }
  const xdg = process.env.XDG_CACHE_HOME;
  if (xdg) return resolve(xdg, "bgs-modding-superpowers", "kb", "packs");
  const home = process.env.HOME || process.env.USERPROFILE || ".";
  return resolve(home, ".cache", "bgs-modding-superpowers", "kb", "packs");
}

export function parseUserPackRoots(envValue: string | undefined): string[] {
  if (!envValue) return [];
  return envValue
    .split(";")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}
