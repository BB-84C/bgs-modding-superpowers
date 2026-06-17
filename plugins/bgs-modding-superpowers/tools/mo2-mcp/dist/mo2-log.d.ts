export interface TailOptions {
    sinceTs?: Date;
    maxBytes?: number;
    maxLines?: number;
}
export interface TailResult {
    lines: string[];
    truncated: boolean;
    logPath: string;
}
export declare function tailMo2Log(mo2Root: string, options?: TailOptions): Promise<TailResult>;
