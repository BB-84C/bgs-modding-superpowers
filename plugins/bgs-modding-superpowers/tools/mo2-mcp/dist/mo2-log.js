/**
 * MO2 log tail reader.
 *
 * Used by pipe-client error enrichment (ENRICHMENT-DESIGN L2) to attach the
 * tail of MO2's interface log to broker failure envelopes, so the agent
 * can see WHY MO2 was unresponsive (modal dialog source, broker exception,
 * `OSError: [Errno 232] The pipe is being closed`, BUG-11's `Cannot launch
 * program` line, etc.) instead of just an opaque timeout message.
 *
 * Failure mode is deliberately silent: missing log, unreadable log, weird
 * encoding — all return `{ lines: [], truncated: false, logPath }`. We never
 * want enrichment failure to mask the underlying broker error.
 *
 * Lines look like:
 *   [2026-06-17 03:44:55.825 I] starting up
 *   [2026-06-17 03:44:56.123 E] Cannot launch program ...
 * Continuation / stack lines without timestamp prefix are kept verbatim.
 */
import { open } from "node:fs/promises";
import { join } from "node:path";
const TIMESTAMP_RE = /^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d{3})/;
const LOG_FILE_CANDIDATES = ["mo_interface.log", "mo2.log"];
export async function tailMo2Log(mo2Root, options = {}) {
    const maxBytes = options.maxBytes ?? 64 * 1024;
    const maxLines = options.maxLines ?? 100;
    let fallbackLogPath = join(mo2Root, "logs", LOG_FILE_CANDIDATES[LOG_FILE_CANDIDATES.length - 1]);
    for (const fileName of LOG_FILE_CANDIDATES) {
        const logPath = join(mo2Root, "logs", fileName);
        fallbackLogPath = logPath;
        const result = await tailLogFile(logPath, { ...options, maxBytes, maxLines });
        if (result)
            return result;
    }
    return { lines: [], truncated: false, logPath: fallbackLogPath };
}
async function tailLogFile(logPath, options) {
    let handle;
    try {
        handle = await open(logPath, "r");
        const stats = await handle.stat();
        const start = Math.max(0, stats.size - options.maxBytes);
        const length = stats.size - start;
        const buf = Buffer.alloc(length);
        if (length > 0) {
            await handle.read(buf, 0, length, start);
        }
        const text = buf.toString("utf8");
        const allLines = text.split(/\r?\n/);
        // If we started mid-line, drop the first (probably partial) line.
        const startLine = start > 0 ? 1 : 0;
        let lines = allLines.slice(startLine).filter((line) => line.length > 0);
        if (options.sinceTs) {
            const sinceMs = options.sinceTs.getTime();
            lines = lines.filter((line) => {
                const match = line.match(TIMESTAMP_RE);
                if (!match)
                    return true; // keep continuation / stack lines
                const tsStr = `${match[1]}T${match[2]}Z`;
                const ms = Date.parse(tsStr);
                if (Number.isNaN(ms))
                    return true;
                return ms >= sinceMs;
            });
        }
        const truncated = lines.length > options.maxLines;
        return {
            lines: truncated ? lines.slice(-options.maxLines) : lines,
            truncated,
            logPath,
        };
    }
    catch {
        return null;
    }
    finally {
        if (handle) {
            await handle.close().catch(() => undefined);
        }
    }
}
