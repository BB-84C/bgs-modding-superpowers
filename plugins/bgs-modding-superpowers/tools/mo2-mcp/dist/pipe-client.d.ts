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
     * Discover the broker pipe via endpoint.json, then smoke-test with
     * system.ping. Throws if discovery or ping fails.
     */
    discoverAndConnect(mo2Root: string, timeoutMs?: number): Promise<void>;
    /**
     * Send one JSON-RPC-shaped request, receive one response, socket closes.
     *
     * Per P-B1: open new connection per call. No pending map.
     */
    call(method: string, payload: Record<string, unknown>, timeoutMs?: number): Promise<BrokerResponse>;
    isConnected(): boolean;
    close(): void;
}
