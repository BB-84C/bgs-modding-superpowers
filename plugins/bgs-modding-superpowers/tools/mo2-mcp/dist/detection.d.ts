export interface DetectionResult {
    processRunning: boolean;
    sharedMemoryPresent: boolean | "unknown";
    profileLockHeld: boolean;
    pid: number | null;
    confidence: "high" | "medium" | "low";
    /** Back-compat broker gate: true when a root-scoped MO2 process is present. */
    online: boolean;
}
export interface DetectionOptions {
    mo2Root: string;
    /** Optional profile dir; signal C lock check is skipped if absent. */
    profileDir?: string;
}
export interface Mo2ProcessInfo {
    pid: number;
    path: string | null;
}
export declare function detectMo2Running(opts: DetectionOptions): Promise<DetectionResult>;
export declare function listMo2ProcessesAtRoot(mo2Root: string): Promise<Mo2ProcessInfo[]>;
