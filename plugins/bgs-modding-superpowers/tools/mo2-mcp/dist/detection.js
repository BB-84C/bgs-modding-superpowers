/**
 * MO2-running detection ladder (3 tiers, Windows-only).
 *
 * Per oracle Open Q5 + S1 librarian-alpha §3.11:
 *   tier 1 (cheap):  process list — ModOrganizer.exe present?
 *   tier 2 (strong): shared-memory probe — mod_organizer_instance_<N> exists?
 *   tier 3 (proof):  profile file exclusive lock — confirms MO2 owns this profile
 *
 * Each tier is optional; higher tier failures fall through. Caller decides
 * confidence threshold via the returned booleans + `online` flag (tier 1+2).
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";
const execFileP = promisify(execFile);
export async function detectMo2Running(opts) {
    let processRunning = false;
    let pid;
    let sharedMemoryPresent = false;
    let profileLockHeld = false;
    try {
        const { stdout } = await execFileP("tasklist", [
            "/FI",
            "IMAGENAME eq ModOrganizer.exe",
            "/FO",
            "CSV",
            "/NH",
        ]);
        const match = stdout.toString().match(/"ModOrganizer\.exe","(\d+)"/);
        if (match) {
            pid = Number.parseInt(match[1], 10);
            processRunning = true;
        }
    }
    catch {
        // tasklist failed or no usable result; keep tier 1 false.
    }
    if (processRunning) {
        try {
            const psScript = `
        $found = $false
        for ($i = 1; $i -le 10; $i++) {
          $name = "mod_organizer_instance_$i"
          try {
            $mmf = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting($name)
            $mmf.Dispose()
            Write-Output $name
            $found = $true
            break
          } catch {}
        }
        if (-not $found) { Write-Output 'none' }
      `;
            const { stdout } = await execFileP("pwsh", ["-NoProfile", "-Command", psScript]);
            sharedMemoryPresent = stdout.toString().trim().startsWith("mod_organizer_instance_");
        }
        catch {
            // PowerShell missing or shared-memory probe failed; keep tier 2 false.
        }
    }
    if (processRunning && opts.profileDir) {
        try {
            const profilePath = opts.profileDir.replace(/\\/g, "\\\\").replace(/'/g, "''");
            const psScript = `
        try {
          $f = [System.IO.File]::Open('${profilePath}\\modlist.txt', 'Open', 'Read', 'None')
          $f.Close()
          Write-Output 'unlocked'
        } catch { Write-Output 'locked' }
      `;
            const { stdout } = await execFileP("pwsh", ["-NoProfile", "-Command", psScript]);
            profileLockHeld = stdout.toString().trim() === "locked";
        }
        catch {
            // Unknown profile-lock state; keep tier 3 false.
        }
    }
    return {
        processRunning,
        sharedMemoryPresent,
        profileLockHeld,
        pid,
        online: processRunning && sharedMemoryPresent,
    };
}
