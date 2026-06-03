import { createWriteStream } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { pipeline } from "node:stream/promises";
import yauzl from "yauzl";

function openZip(zipPath: string): Promise<yauzl.ZipFile> {
  return new Promise((resolveOpen, reject) => {
    yauzl.open(zipPath, { lazyEntries: true }, (error, zip) => {
      if (error || !zip) reject(error ?? new Error("Failed to open zip"));
      else resolveOpen(zip);
    });
  });
}

function openReadStream(zip: yauzl.ZipFile, entry: yauzl.Entry): Promise<NodeJS.ReadableStream> {
  return new Promise((resolveStream, reject) => {
    zip.openReadStream(entry, (error, stream) => {
      if (error || !stream) reject(error ?? new Error(`Failed to read zip entry ${entry.fileName}`));
      else resolveStream(stream);
    });
  });
}

export async function extractZip(zipPath: string, destDir: string): Promise<void> {
  await mkdir(destDir, { recursive: true });
  const destRoot = resolve(destDir);
  const zip = await openZip(zipPath);
  try {
    await new Promise<void>((resolveDone, reject) => {
      zip.on("error", reject);
      zip.on("end", resolveDone);
      zip.on("entry", (entry: yauzl.Entry) => {
        void (async () => {
          const fileName = entry.fileName.replace(/\\/g, "/");
          const outPath = resolve(destRoot, fileName);
          if (!outPath.startsWith(destRoot)) throw new Error(`Unsafe zip entry path: ${entry.fileName}`);
          if (/\/$/.test(fileName)) {
            await mkdir(outPath, { recursive: true });
          } else {
            await mkdir(dirname(outPath), { recursive: true });
            await pipeline(await openReadStream(zip, entry), createWriteStream(outPath));
          }
          zip.readEntry();
        })().catch(reject);
      });
      zip.readEntry();
    });
  } finally {
    zip.close();
  }
}
