/**
 * INI editing helpers — section/key upsert preserving other content.
 *
 * Per PLAN-PATCH P-F2: shared by S4 metadata tools.
 */
/** Upsert a value into [section] key= in INI text. Appends section if missing. */
export declare function upsertIniValue(text: string, section: string, key: string, value: string): string;
