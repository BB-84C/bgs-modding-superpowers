export interface ProfileMod {
    name: string;
    priority: number;
    enabled: boolean;
    isSeparator: boolean;
}
export interface ProfilePlugin {
    name: string;
    enabled: boolean;
    isComment: boolean;
}
export interface Profile {
    path: string;
    name: string;
    mods: ProfileMod[];
    plugins: ProfilePlugin[];
    modlistMtimeMs: number;
    pluginsMtimeMs: number;
}
export declare function readProfile(profileDir: string): Promise<Profile>;
