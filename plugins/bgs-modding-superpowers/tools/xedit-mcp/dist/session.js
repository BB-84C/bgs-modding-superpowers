export async function buildContext(opts) {
    const { adapter, sessionId } = opts;
    const [describeRes, capsRes, filesRes] = await Promise.all([
        adapter.call({ command: "system.describe", args: {} }),
        adapter.call({ command: "system.capabilities", args: {} }),
        adapter.call({ command: "files.list", args: {} }),
    ]);
    const describe = describeRes.ok ? describeRes.result : {};
    const caps = capsRes.ok ? capsRes.result : {};
    const filesResult = filesRes.ok ? filesRes.result : {};
    // The daemon returns files as an array of objects (`{name, loadOrder, fileName, ...}`),
    // while unit-test mocks supply a plain `string[]`. Accept both shapes and extract the
    // canonical plugin name (preferring `name`, falling back to `fileName`).
    const loadOrder = Array.isArray(filesResult.files)
        ? filesResult.files
            .map((f) => {
            if (typeof f === "string")
                return f;
            if (f && typeof f === "object") {
                const obj = f;
                if (typeof obj.name === "string")
                    return obj.name;
                if (typeof obj.fileName === "string")
                    return obj.fileName;
            }
            return "";
        })
            .filter((s) => s.length > 0)
        : [];
    const supports = (caps.supports ?? {});
    const capabilities = {
        contractVersion: String(caps.contractVersion ?? "unknown"),
        // Prefer the friendly `gameName` ("Fallout4") over the internal `gameMode`
        // token ("gmFO4"). Fall back to gameMode for adapters/tests that only set
        // the latter (e.g. the existing unit test mock).
        gameMode: String(describe.gameName ?? describe.gameMode ?? "unknown"),
        commands: Array.isArray(caps.commands) ? caps.commands : [],
        supports,
        fetchedAt: new Date().toISOString(),
    };
    // Consent is advertised by the daemon under the supports tree, but NOT at the
    // top level. xEdit r6 places the same boolean under TWO nested keys (both
    // reflect the single `-IKnowWhatImDoing` CLI flag):
    //   supports.elementsMutation.iKnowWhatImDoing
    //   supports.scripts.execution.iKnowWhatImDoing
    // Empirically verified 2026-06-18 against FO4Edit 4.1.6r6 daemon: launching
    // with the flag set both nested keys to `true` and left `supports.iKnowWhatImDoing`
    // (top-level) undefined. The pre-r6 code path read the non-existent top-level
    // field and projected `consentEnabled: false` regardless of the flag — that
    // bug was invisible until issue #8 wired the flag forwarding end-to-end. Read
    // either nested path (we OR them for robustness against future schema shifts).
    const elementsMutation = (supports.elementsMutation ?? {});
    const scriptsBlock = (supports.scripts ?? {});
    const scriptsExec = (scriptsBlock.execution ?? {});
    const consentEnabled = elementsMutation.iKnowWhatImDoing === true ||
        scriptsExec.iKnowWhatImDoing === true;
    return {
        sessionId,
        daemonPid: opts.daemonPid,
        mcpModeActive: opts.mcpModeActive ?? false,
        loadOrder,
        consentEnabled,
        capabilities,
    };
}
//# sourceMappingURL=session.js.map