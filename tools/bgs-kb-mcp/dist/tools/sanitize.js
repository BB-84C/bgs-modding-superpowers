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
export function sanitizeFtsQuery(rawQuery) {
    const tokens = tokenizePreservingQuotes(rawQuery.trim());
    const sanitized = tokens
        .map((token) => (token.quoted ? sanitizeQuoted(token.value) : sanitizeBare(token.value)))
        .filter((token) => token.length > 0);
    return sanitized.join(" ");
}
function tokenizePreservingQuotes(input) {
    const tokens = [];
    let current = "";
    let quoted = false;
    for (const ch of input) {
        if (ch === '"') {
            if (quoted) {
                tokens.push({ value: current, quoted: true });
                current = "";
                quoted = false;
            }
            else {
                if (current.trim())
                    tokens.push({ value: current.trim(), quoted: false });
                current = "";
                quoted = true;
            }
            continue;
        }
        if (!quoted && /\s/.test(ch)) {
            if (current.trim())
                tokens.push({ value: current.trim(), quoted: false });
            current = "";
            continue;
        }
        current += ch;
    }
    if (current.trim())
        tokens.push({ value: current.trim(), quoted });
    return tokens;
}
function sanitizeQuoted(value) {
    const cleaned = value.replace(/[()^*:?!,;]/g, "").replace(/\s+/g, " ").trim();
    return cleaned.length > 0 ? `"${cleaned}"` : "";
}
function sanitizeBare(value) {
    const cleaned = value
        .replace(/(^|\s)-+/g, "$1")
        .replace(/[()^*:?!,;"]/g, "")
        .replace(/\s+/g, " ")
        .trim();
    if (cleaned.length === 0)
        return "";
    // Wrap as a phrase if the token contains anything other than letters,
    // digits, or underscores. This covers dots (plugins.txt), internal
    // hyphens (mis-attribution, CP-1252, UTF-8, BB84-philosophy), slashes,
    // and any other surviving punctuation that would confuse FTS5's query
    // parser — which can interpret unfamiliar hyphen-bearing tokens as
    // column references and crash with "no such column: <suffix>".
    return /^[\p{L}\p{N}_]+$/u.test(cleaned) ? cleaned : `"${cleaned}"`;
}
//# sourceMappingURL=sanitize.js.map