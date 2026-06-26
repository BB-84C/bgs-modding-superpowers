let _staleBrokerWarningEmitted = false;
export async function pollPluginWarnings(pipeClient, names) {
    try {
        const resp = await pipeClient.call("plugins.missing_masters", names ? { names } : {});
        if (resp?.error) {
            if (resp.error.code === "method_not_found") {
                if (!_staleBrokerWarningEmitted) {
                    process.stderr.write("[mo2-mcp] plugins.missing_masters not in deployed broker. " +
                        "Run install-mo2-control-plane.ps1 -Force and restart MO2 to enable missing-master warnings.\n");
                    _staleBrokerWarningEmitted = true;
                }
                return {
                    warnings: [],
                    scannedCount: 0,
                    enabledCount: 0,
                    pollFailed: "broker_stale_missing_masters_handler_not_deployed",
                };
            }
            return {
                warnings: [],
                scannedCount: 0,
                enabledCount: 0,
                pollFailed: resp.error.message ?? `broker_error_${resp.error.code}`,
            };
        }
        const result = ((resp?.result ?? resp) ?? {});
        const rawWarnings = Array.isArray(result.warnings) ? result.warnings : [];
        return {
            warnings: rawWarnings.map((w) => ({
                plugin: String(w.plugin ?? ""),
                missingMasters: Array.isArray(w.missing_masters) ? w.missing_masters.map(String) : [],
                enabledMasters: Array.isArray(w.enabled_masters) ? w.enabled_masters.map(String) : [],
                declaredMasters: Array.isArray(w.declared_masters) ? w.declared_masters.map(String) : [],
            })),
            scannedCount: Number(result.scanned_count ?? 0),
            enabledCount: Number(result.enabled_count ?? 0),
        };
    }
    catch (err) {
        return {
            warnings: [],
            scannedCount: 0,
            enabledCount: 0,
            pollFailed: err instanceof Error ? err.message : String(err),
        };
    }
}
