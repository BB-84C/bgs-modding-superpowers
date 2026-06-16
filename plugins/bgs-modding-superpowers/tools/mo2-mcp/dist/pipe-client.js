/**
 * Named-pipe broker client (Windows).
 *
 * Per PLAN-PATCH P-B1: the broker (mo2_agent_control.py) accepts exactly one
 * request per pipe connection, then disconnects. We open a fresh net.Socket
 * per call() and never multiplex. No request_id pending map — call/response
 * is 1:1 by socket lifetime.
 *
 * Discovery: read endpoint.json published by the broker plugin at
 * <MO2_Root>/plugins/Mo2AgentControl/bootstrap/runtime/endpoint.json.
 */
import { connect } from "node:net";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { listMo2ProcessesAtRoot } from "./detection.js";
export class PipeClient {
    pipeName;
    connectedOnce = false;
    /**
     * Discover the broker pipe via endpoint.json, then smoke-test with
     * system.ping. Throws if discovery or ping fails.
     */
    async discoverAndConnect(mo2Root, timeoutMs = 5000, _options = {}) {
        const endpointPath = join(mo2Root, "plugins", "Mo2AgentControl", "bootstrap", "runtime", "endpoint.json");
        const errors = [];
        const endpoint = await readEndpoint(endpointPath, mo2Root);
        const endpointPid = endpointPidFrom(endpoint);
        if (endpointPid === undefined || isPidAlive(endpointPid)) {
            if (await this.tryConnect(endpoint.endpoint, timeoutMs, errors))
                return;
            this.pipeName = undefined;
            throw new Error(`broker pipe discovery failed; tried ${errors.join("; ")}`);
        }
        const matchingProcesses = await listMo2ProcessesAtRoot(mo2Root);
        if (matchingProcesses.length === 0) {
            this.pipeName = undefined;
            throw new Error(`endpoint_stale_no_matching_mo2_at_root: ${mo2Root}`);
        }
        const refreshed = await readEndpoint(endpointPath, mo2Root);
        const refreshedPid = endpointPidFrom(refreshed);
        if (refreshedPid !== undefined && !matchingProcesses.some((process) => process.pid === refreshedPid)) {
            this.pipeName = undefined;
            throw new Error(`endpoint_stale_no_matching_mo2_at_root: ${mo2Root}`);
        }
        if (await this.tryConnect(refreshed.endpoint, timeoutMs, errors))
            return;
        this.pipeName = undefined;
        throw new Error(`broker pipe discovery failed; tried ${errors.join("; ")}`);
    }
    async tryConnect(endpoint, timeoutMs, errors) {
        const candidate = pipeNameOnly(endpoint);
        this.pipeName = candidate;
        try {
            await this.call("system.ping", {}, timeoutMs);
            this.connectedOnce = true;
            return true;
        }
        catch (e) {
            const message = e instanceof Error ? e.message : String(e);
            errors.push(`${toPipePath(candidate)}: ${message}`);
            this.pipeName = undefined;
            return false;
        }
    }
    /**
     * Send one JSON-RPC-shaped request, receive one response, socket closes.
     *
     * Per P-B1: open new connection per call. No pending map.
     */
    async call(method, payload, timeoutMs = 30000) {
        if (!this.pipeName) {
            throw new Error("pipe not discovered (call discoverAndConnect first)");
        }
        const id = `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
        const request = {
            protocol_version: "1",
            request_id: id,
            session_id: "mo2-mcp",
            method,
            payload,
        };
        const path = toPipePath(this.pipeName);
        return new Promise((resolve, reject) => {
            const socket = connect(path);
            let buffer = "";
            let settled = false;
            const finishReject = (err) => {
                if (settled)
                    return;
                settled = true;
                clearTimeout(timer);
                reject(err);
            };
            const finishResolve = (response) => {
                if (settled)
                    return;
                settled = true;
                clearTimeout(timer);
                resolve(response);
            };
            const timer = setTimeout(() => {
                socket.destroy();
                finishReject(new Error(`pipe call timeout (${method})`));
            }, timeoutMs);
            socket.once("connect", () => {
                socket.write(`${JSON.stringify(request)}\n`);
            });
            socket.on("data", (chunk) => {
                buffer += chunk.toString("utf8");
            });
            socket.on("close", () => {
                const firstLine = buffer.split("\n")[0];
                if (!firstLine) {
                    finishReject(new Error(`empty pipe response (${method})`));
                    return;
                }
                try {
                    finishResolve(JSON.parse(firstLine));
                }
                catch (e) {
                    const message = e instanceof Error ? e.message : String(e);
                    finishReject(new Error(`pipe response parse error: ${message}`));
                }
            });
            socket.once("error", (err) => {
                if (isPipeCloseAfterResponseError(err)) {
                    return;
                }
                finishReject(err);
            });
        });
    }
    isConnected() {
        return this.connectedOnce;
    }
    close() {
        this.connectedOnce = false;
    }
}
function toPipePath(name) {
    const stripped = name.replace(/^\\\\\.\\pipe\\/i, "");
    return `\\\\.\\pipe\\${stripped}`;
}
function isPipeCloseAfterResponseError(err) {
    return err.code === "EPIPE" || err.code === "ECONNRESET";
}
function pipeNameOnly(name) {
    return name.replace(/^\\\\\.\\pipe\\/i, "");
}
async function readEndpoint(endpointPath, mo2Root) {
    let text;
    try {
        text = await readFile(endpointPath, "utf8");
    }
    catch {
        throw new Error(`no_endpoint_found_at_root: ${mo2Root}`);
    }
    const endpoint = JSON.parse(text);
    if (!endpoint.endpoint) {
        throw new Error(`endpoint.json has no 'endpoint' field: ${endpointPath}`);
    }
    return { endpoint: endpoint.endpoint, pid: endpoint.pid };
}
function endpointPidFrom(endpoint) {
    if (Number.isInteger(endpoint.pid) && endpoint.pid > 0)
        return endpoint.pid;
    const match = pipeNameOnly(endpoint.endpoint).match(/(\d+)$/);
    if (!match)
        return undefined;
    const pid = Number.parseInt(match[1], 10);
    return Number.isInteger(pid) && pid > 0 ? pid : undefined;
}
function isPidAlive(pid) {
    try {
        process.kill(pid, 0);
        return true;
    }
    catch (error) {
        const code = error.code;
        return code !== "ESRCH";
    }
}
