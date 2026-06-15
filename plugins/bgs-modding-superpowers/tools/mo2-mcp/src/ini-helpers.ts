/**
 * INI editing helpers — section/key upsert preserving other content.
 *
 * Per PLAN-PATCH P-F2: shared by S4 metadata tools.
 */

/** Upsert a value into [section] key= in INI text. Appends section if missing. */
export function upsertIniValue(
  text: string,
  section: string,
  key: string,
  value: string,
): string {
  const lines = text.split(/\r?\n/);
  let inSection = false;
  let sectionFoundIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed === `[${section}]`) {
      inSection = true;
      sectionFoundIdx = i;
      continue;
    }
    if (inSection && trimmed.startsWith("[")) {
      inSection = false;
    }
    if (inSection && trimmed.startsWith(`${key}=`)) {
      lines[i] = `${key}=${value}`;
      return lines.join("\n");
    }
  }
  if (sectionFoundIdx >= 0) {
    lines.splice(sectionFoundIdx + 1, 0, `${key}=${value}`);
    return lines.join("\n");
  }
  return text + (text.endsWith("\n") ? "" : "\n") + `[${section}]\n${key}=${value}\n`;
}
