export interface SnapshotFile {
    source: string;
    kind: "file" | "directory" | "absent";
    backup: string;
}
export interface SnapshotRecord {
    snapshotId: string;
    tool: string;
    ts: string;
    files: SnapshotFile[];
}
export declare class SnapshotManager {
    private snapshotRoot;
    private sessionId;
    constructor(snapshotRoot: string, sessionId: string);
    /** Find a manifest record by snapshotId across this session's snapshot dirs. */
    findManifest(snapshotId: string): Promise<SnapshotRecord | undefined>;
    /**
     * Snapshot a set of source files/directories into a new dir under the session.
     * Returns the SnapshotRecord with snapshotId; sources that do not exist yet
     * are recorded as absent so restore can remove newly-created paths.
     */
    snapshot(tool: string, sourceFiles: string[]): Promise<SnapshotRecord>;
    /**
     * Restore files from a snapshot identified by snapshotId.
     * Returns lists of restored + failed source paths.
     */
    restore(snapshotId: string): Promise<{
        restored: string[];
        failed: string[];
    }>;
}
