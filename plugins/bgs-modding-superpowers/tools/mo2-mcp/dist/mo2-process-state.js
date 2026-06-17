/**
 * MO2 process responsiveness probe (Windows).
 *
 * Used by pipe-client error enrichment (ENRICHMENT-DESIGN L1) to distinguish
 * an opaque "pipe call timeout" from "MO2 GUI is frozen on a modal dialog".
 * When MO2's main Qt thread is blocked (modal dialog, long-running operation,
 * mods.set_active stuck under a `Cannot launch program` dialog from BUG-11),
 * the OS marks the process as not-responding. Reporting that distinction to
 * the agent unblocks BUG-16 triage.
 *
 * See `.opencode/artifacts/mo2-mcp/e2e-test-plan/run-20260617T002922Z/ENRICHMENT-DESIGN.md`
 * and BUGS.md BUG-16 for the load-bearing motivation.
 *
 * Scoping note: this helper deliberately filters by `mo2Root` (using the same
 * pattern as detection.ts signal A) so a probe never matches an MO2 process
 * outside the bound root. Fails closed: any error returns { alive: false }.
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";
const execFileP = promisify(execFile);
export async function probeMo2Process(mo2Root) {
    try {
        // PowerShell single-quoted strings escape ' as ''. mo2Root may contain
        // spaces (e.g. "B:\WastelandBlues 2.0") but not single quotes in normal use.
        const escapedRoot = mo2Root.replace(/'/g, "''");
        const psScript = `
      $procs = Get-Process -Name 'ModOrganizer*' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path -like '${escapedRoot}\\*' } |
        Select-Object Id, Responding, @{N='StartTime';E={ try { $_.StartTime.ToString('o') } catch { $null } }}
      if ($procs) { $procs | ConvertTo-Json -Compress }
    `;
        const { stdout } = await execFileP("pwsh", ["-NoProfile", "-Command", psScript]);
        const trimmed = stdout.toString().trim();
        if (!trimmed)
            return { alive: false };
        const parsed = JSON.parse(trimmed);
        const proc = Array.isArray(parsed) ? parsed[0] : parsed;
        if (!proc || typeof proc.Id !== "number")
            return { alive: false };
        return {
            alive: true,
            pid: proc.Id,
            responding: typeof proc.Responding === "boolean" ? proc.Responding : undefined,
            startTime: typeof proc.StartTime === "string" ? proc.StartTime : undefined,
        };
    }
    catch {
        return { alive: false };
    }
}
