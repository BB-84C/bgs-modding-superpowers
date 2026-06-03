/**
 * Conflict verdict mapping shared across record-side tools.
 *
 * Lifted from `tools/inspect-conflicts.ts` in Batch 2 (carry-forward #6) so
 * future record-side tools (e.g. `xedit_diff_records`, `xedit_explain_winner`)
 * speak one verdict vocabulary against the xEdit fork. If the fork ever
 * renames its `caXxx` enum, this is the single seam to update.
 *
 * xEdit conflict-all enum (from `records.conflict_status` -> `result.conflict.all`):
 *  - caUnknown / caOnlyOne / caNoConflict   -> no_conflict
 *  - caITM                                  -> itm   (identical to master)
 *  - caITPO                                 -> itpo  (identical to previous override)
 *  - caOverride / caConflictBenign          -> minor (override present, content benign)
 *  - caConflict                             -> minor (real semantic conflict)
 *  - caConflictCritical                     -> breaking
 *
 * Legacy flat string statuses (e.g. unit-test mocks that send "no_conflict",
 * "conflict_critical", "ITPO") are still recognized so call-site mocks do not
 * have to be rewritten every time the daemon vocabulary shifts.
 */
export type Verdict = "no_conflict" | "itpo" | "itm" | "minor" | "breaking";

export function mapVerdict(status: string): Verdict {
  const s = status.toLowerCase();
  if (s === "caitpo" || s.includes("itpo")) return "itpo";
  if (s === "caitm" || s.includes("itm")) return "itm";
  if (
    s === "caunknown" ||
    s === "caonlyone" ||
    s === "canoconflict" ||
    s === "no_conflict" ||
    s === "no conflict"
  ) {
    return "no_conflict";
  }
  if (s === "caconflictcritical" || s.includes("critical") || s.includes("breaking")) {
    return "breaking";
  }
  if (s === "caoverride" || s === "caconflictbenign") return "minor";
  if (s === "caconflict") return "minor";
  if (s.includes("conflict")) return "minor";
  return "minor";
}
