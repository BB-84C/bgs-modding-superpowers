export interface DetectionResult {
    processRunning: boolean;
    sharedMemoryPresent: boolean;
    profileLockHeld: boolean;
    pid?: number;
    /** True when both tier 1 + tier 2 pass — high-confidence MO2 alive. */
    online: boolean;
}
export interface DetectionOptions {
    mo2Root: string;
    /** Optional profile dir; tier 3 lock check is skipped if absent. */
    profileDir?: string;
}
export declare function detectMo2Running(opts: DetectionOptions): Promise<DetectionResult>;
