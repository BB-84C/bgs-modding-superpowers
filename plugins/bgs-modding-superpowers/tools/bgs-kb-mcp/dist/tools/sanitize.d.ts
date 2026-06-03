/**
 * Convert agent free text into a conservative FTS5 MATCH expression.
 *
 * Rules for v1:
 * - Preserve quoted phrases for power users.
 * - Strip common FTS5 operator/metacharacter punctuation from unquoted terms.
 * - Strip leading '-' so accidental boolean NOT syntax is not interpreted.
 * - Wrap bare dot-bearing tokens (plugins.txt) as phrases so unicode61 tokenization
 *   treats the split tokens as adjacent phrase terms.
 */
export declare function sanitizeFtsQuery(rawQuery: string): string;
