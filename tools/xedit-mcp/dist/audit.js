import { mkdir, appendFile } from "node:fs/promises";
import { join } from "node:path";
export function createAuditLogger(opts) {
    const now = opts.now ?? (() => new Date());
    const onError = opts.onError ?? (() => { });
    return {
        async append(record) {
            try {
                const ts = now();
                const day = ts.toISOString().slice(0, 10);
                const line = JSON.stringify({ ...record, ts: ts.toISOString() }) + "\n";
                const filePath = join(opts.baseDir, `${day}.jsonl`);
                await mkdir(opts.baseDir, { recursive: true });
                await appendFile(filePath, line, "utf8");
            }
            catch (err) {
                try {
                    onError(err);
                }
                catch {
                    /* swallow callback's own throws to honour the never-throws contract */
                }
            }
        },
    };
}
//# sourceMappingURL=audit.js.map