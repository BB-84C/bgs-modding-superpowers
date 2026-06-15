export interface LeaseComponent {
    path: string;
    kind: "text-file" | "directory";
    /** Set for text-file: sha256 of full content. */
    contentHash?: string;
    /** Set for text-file: byte length. */
    size?: number;
    /** Set for directory: count of files (recursively). */
    fileCount?: number;
    /** Set for directory: sum of file sizes (bytes). */
    totalSize?: number;
}
export interface Lease {
    token: string;
    components: LeaseComponent[];
}
export interface LeaseTarget {
    path: string;
    kind: "text-file" | "directory";
}
export declare function fingerprintFile(path: string): Promise<LeaseComponent>;
export declare function fingerprintDir(path: string): Promise<LeaseComponent>;
export declare function computeLease(targets: LeaseTarget[]): Promise<Lease>;
export interface LeaseDrift {
    path: string;
    planComponent: LeaseComponent;
    currentComponent: LeaseComponent;
}
export declare function verifyLease(lease: Lease): Promise<{
    valid: true;
} | {
    valid: false;
    drift: LeaseDrift[];
}>;
