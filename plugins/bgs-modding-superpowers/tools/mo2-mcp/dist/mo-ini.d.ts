export interface MoIniCustomExecutable {
    title: string;
    binary: string;
    arguments?: string;
    workingDirectory?: string;
    steamAppID?: string;
    ownicon?: boolean;
    hide?: boolean;
    toolbar?: boolean;
    minimizeToSystemTray?: boolean;
}
export interface MoIni {
    raw: string;
    general: {
        game?: string;
        gameName?: string;
        gamePath?: string;
        selectedProfile?: string;
    };
    settings: {
        baseDirectory?: string;
        modDirectory?: string;
        downloadDirectory?: string;
        profilesDirectory?: string;
        overwriteDirectory?: string;
        cacheDirectory?: string;
    };
    customExecutables: MoIniCustomExecutable[];
    /** Section name -> [startLine, endLine] inclusive, zero-based line numbers in `raw`. */
    sectionRanges: Map<string, [number, number]>;
}
export declare function readMoIni(path: string): Promise<MoIni>;
