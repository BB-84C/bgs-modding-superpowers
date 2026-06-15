import { z } from "zod";
export declare const ConfigSchema: z.ZodObject<{
    permission_ceiling: z.ZodDefault<z.ZodEnum<["read-only", "metadata-editable", "full-control"]>>;
    allowed_profiles: z.ZodDefault<z.ZodArray<z.ZodString, "many">>;
    deny: z.ZodDefault<z.ZodArray<z.ZodString, "many">>;
    snapshot_root: z.ZodDefault<z.ZodString>;
    audit_root: z.ZodDefault<z.ZodString>;
}, "strict", z.ZodTypeAny, {
    permission_ceiling: "read-only" | "metadata-editable" | "full-control";
    allowed_profiles: string[];
    deny: string[];
    snapshot_root: string;
    audit_root: string;
}, {
    permission_ceiling?: "read-only" | "metadata-editable" | "full-control" | undefined;
    allowed_profiles?: string[] | undefined;
    deny?: string[] | undefined;
    snapshot_root?: string | undefined;
    audit_root?: string | undefined;
}>;
export type RawConfig = z.infer<typeof ConfigSchema>;
export interface Config {
    mo2Root: string;
    permissionCeiling: RawConfig["permission_ceiling"];
    allowedProfiles: string[];
    deny: string[];
    snapshotRoot: string;
    auditRoot: string;
}
export declare function loadConfig(opts: {
    mo2Root: string;
}): Promise<Config>;
