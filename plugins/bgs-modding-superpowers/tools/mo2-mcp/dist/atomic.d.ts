/** Atomically write text content to `path`. Creates parent dirs if missing. */
export declare function atomicWriteText(path: string, content: string, encoding?: BufferEncoding): Promise<void>;
/** Atomically write binary content to `path`. */
export declare function atomicWriteBytes(path: string, content: Buffer): Promise<void>;
