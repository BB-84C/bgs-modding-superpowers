import matter from "gray-matter";
import { readdir, readFile } from "node:fs/promises";
import { join, relative, sep } from "node:path";
async function walkMarkdownFiles(root) {
    const entries = await readdir(root, { withFileTypes: true });
    const paths = await Promise.all(entries.map(async (entry) => {
        const fullPath = join(root, entry.name);
        if (entry.isDirectory())
            return walkMarkdownFiles(fullPath);
        if (entry.isFile() && entry.name.endsWith(".md"))
            return [fullPath];
        return [];
    }));
    return paths.flat().sort((a, b) => a.localeCompare(b));
}
function toSourcePath(packRoot, filePath) {
    return relative(packRoot, filePath).split(sep).join("/");
}
export async function readRecords(packRoot) {
    const recordsRoot = join(packRoot, "records");
    const files = await walkMarkdownFiles(recordsRoot);
    const records = [];
    for (const file of files) {
        const raw = await readFile(file, "utf8");
        const parsed = matter(raw);
        if (parsed.data._draft === true)
            continue;
        records.push({
            ...parsed.data,
            sourcePath: toSourcePath(packRoot, file),
            bodyMd: parsed.content,
        });
    }
    return records;
}
//# sourceMappingURL=read-records.js.map