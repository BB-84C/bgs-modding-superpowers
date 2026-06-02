export function mapVerdict(status) {
    const s = status.toLowerCase();
    if (s === "caitpo" || s.includes("itpo"))
        return "itpo";
    if (s === "caitm" || s.includes("itm"))
        return "itm";
    if (s === "caunknown" ||
        s === "caonlyone" ||
        s === "canoconflict" ||
        s === "no_conflict" ||
        s === "no conflict") {
        return "no_conflict";
    }
    if (s === "caconflictcritical" || s.includes("critical") || s.includes("breaking")) {
        return "breaking";
    }
    if (s === "caoverride" || s === "caconflictbenign")
        return "minor";
    if (s === "caconflict")
        return "minor";
    if (s.includes("conflict"))
        return "minor";
    return "minor";
}
//# sourceMappingURL=verdict.js.map