export interface Mo2ProcessState {
    alive: boolean;
    pid?: number;
    responding?: boolean;
    startTime?: string;
}
export declare function probeMo2Process(mo2Root: string): Promise<Mo2ProcessState>;
