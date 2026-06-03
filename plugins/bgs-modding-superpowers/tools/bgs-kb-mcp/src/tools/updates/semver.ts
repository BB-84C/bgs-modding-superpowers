export function parseVersion(version: string | undefined): [number, number, number] {
  if (!version) return [0, 0, 0];
  const normalized = version.replace(/^v/i, "").split("-")[0];
  const parts = normalized.split(".");
  if (parts.length > 3) return [0, 0, 0];
  const parsed = parts.map((part) => (/^\d+$/.test(part) ? Number(part) : Number.NaN));
  if (parsed.some((part) => Number.isNaN(part))) return [0, 0, 0];
  return [parsed[0] ?? 0, parsed[1] ?? 0, parsed[2] ?? 0];
}

export function compareVersions(a: string | undefined, b: string | undefined): number {
  const left = parseVersion(a);
  const right = parseVersion(b);
  for (let i = 0; i < 3; i += 1) {
    if (left[i] !== right[i]) return left[i] - right[i];
  }
  return 0;
}
