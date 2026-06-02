import { fallbackPackId, type PackInfo } from "./index.js";

function valueOrMissing(value: string | number | undefined): string {
  return value === undefined || value === "" ? "(not available)" : String(value);
}

function shortHash(value: string | undefined): string {
  return value ? value.slice(0, 12) : "(not available)";
}

function line(label: string, value: string): string {
  return `${label.padEnd(16)}${value}`;
}

function formatCounts(counts: Record<string, number>): string[] {
  return Object.entries(counts).map(([key, count]) => `  ${key}: ${count}`);
}

function recordsLine(info: PackInfo): string {
  if (info.manifest && info.sqlite) return `${info.manifest.recordCount} (manifest) / ${info.sqlite.recordCount} (kb.sqlite)`;
  if (info.manifest) return `${info.manifest.recordCount} (manifest)`;
  if (info.sqlite) return `${info.derivedRecordCount} (records/) / ${info.sqlite.recordCount} (kb.sqlite)`;
  return `${info.derivedRecordCount} (records/)`;
}

function sha256Verified(value: boolean | undefined): string {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "n/a";
}

export function formatInfo(info: PackInfo): string {
  const manifest = info.manifest;
  const lines: string[] = [];
  for (const warning of info.warnings) lines.push(`WARN: ${warning}`);
  if (lines.length > 0) lines.push("");

  lines.push(line("Pack:", fallbackPackId(info)));
  lines.push(line("Display name:", valueOrMissing(manifest?.displayName ?? fallbackPackId(info))));
  lines.push(line("Version:", valueOrMissing(manifest?.version)));
  lines.push(line("Schema version:", valueOrMissing(manifest?.schemaVersion)));
  lines.push(line("Min plugin:", valueOrMissing(manifest?.minPluginVersion)));
  lines.push(line("Owner:", valueOrMissing(manifest?.owner)));
  lines.push(line("License:", valueOrMissing(manifest?.license)));
  lines.push(line("Built at:", valueOrMissing(manifest?.builtAt)));
  lines.push(line("Source commit:", shortHash(manifest?.sourceCommit)));
  lines.push("");
  lines.push(line("Records:", recordsLine(info)));
  lines.push(line("Domains:", info.domains.join(", ") || "(none)"));
  lines.push(line("Games:", info.games.join(", ") || "(none)"));
  lines.push(line("Engine fams:", info.engineFamilies.join(", ") || "(none)"));
  lines.push("");
  if (info.sqlite) {
    lines.push(line("kb.sqlite:", `${info.sqlite.path} (${info.sqlite.sizeBytes} bytes, sha256 ${shortHash(info.sqlite.sha256)})`));
    lines.push(`${"".padEnd(16)}sha256 verified: ${sha256Verified(info.sqlite.sha256Verified)}`);
  } else {
    lines.push(line("kb.sqlite:", `${info.sqlitePath} (missing)`));
  }
  lines.push(line("manifest.json:", manifest ? info.manifestPath : `${info.manifestPath} (missing)`));
  lines.push("");
  lines.push("By domain:");
  lines.push(...formatCounts(info.byDomain));
  lines.push("By game (a record may apply to multiple games):");
  lines.push(...formatCounts(info.byGame));
  return `${lines.join("\n")}\n`;
}
