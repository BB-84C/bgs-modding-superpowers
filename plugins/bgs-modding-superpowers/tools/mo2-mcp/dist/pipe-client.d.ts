export interface BrokerResponse {
    ok: boolean;
    result?: unknown;
    error?: {
        code: string;
        message: string;
    };
}
export declare class PipeClient {
    private pipeName?;
    private connectedOnce;
    /**
     * MO2 root remembered from discoverAndConnect(), used by call() to drive
     * L1 (process state) and L2 (log tail) enrichment when a broker call
     * fails. Optional because tests and one-off scripts can construct a
     * PipeClient without ever calling discoverAndConnect.
     */
    private mo2Root?;
    /**
     * Discover the broker pipe via endpoint.json, then smoke-test with
     * system.ping. Throws if discovery or ping fails.
     */
    discoverAndConnect(mo2Root: string, timeoutMs?: number, _options?: {
        expectedPid?: number;
    }): Promise<void>;
    private tryConnect;
    /**
     * Send one JSON-RPC-shaped request, receive one response, socket closes.
     *
     * Per P-B1: open new connection per call. No pending map.
     *
     * Wraps `_rawCall` with L1+L2 enrichment (ENRICHMENT-DESIGN.md, Lane B): on
     * failure, probe MO2 process state, tail mo2.log, and throw a typed
     * BrokerEnrichedError so dispatch.ts can surface a structured envelope.
     * The bare ``pipe not discovered`` precondition rejects synchronously and
     * is NOT enriched (no MO2 root yet to probe).
     */
    call(method: string, payload: Record<string, unknown>, timeoutMs?: number): Promise<BrokerResponse>;
    /**
     * Re-read endpoint.json and update the cached pipeName if it has changed.
     *
     * Used by `call()` to recover transparently when MO2 has been restarted
     * since the original `discoverAndConnect`. We deliberately do NOT re-run
     * the full discoverAndConnect cycle here:
     *   - the broker publishes the new endpoint.json on every startup, so a
     *     simple file read is enough to learn the new pipename;
     *   - the full ping cycle would block every T3 dispatch in the steady-state
     *     "pipe is still healthy" path, which is the overwhelming majority of
     *     calls.
     *
     * If `endpoint.json` cannot be read (MO2 closed, plugin removed, IO
     * race), this method silently returns; the subsequent `_rawCall` will
     * fail normally and L1/L2 enrichment kicks in. This keeps the stale-pipe
     * recovery best-effort and never adds a new failure mode.
     */
    _maybeRefreshStaleEndpoint(): Promise<void>;
    /**
     * Raw broker call. Throws plain Error on timeout / empty / parse / socket
     * failure. Callers should prefer `call()` which adds L1+L2 enrichment;
     * `_rawCall` is exposed only for the in-class wrapping seam.
     */
    private _rawCall;
    isConnected(): boolean;
    close(): void;
}
