import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
export async function sha256File(path) {
    return await new Promise((resolve, reject) => {
        const hash = createHash("sha256");
        const stream = createReadStream(path);
        stream.on("data", (chunk) => hash.update(chunk));
        stream.on("error", reject);
        stream.on("end", () => resolve(hash.digest("hex")));
    });
}
//# sourceMappingURL=sha256.js.map