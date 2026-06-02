import * as Ajv2020Module from "ajv/dist/2020.js";
import type { ErrorObject } from "ajv/dist/2020.js";
import * as addFormatsModule from "ajv-formats";
import { existsSync, readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";

import type { SourceRecord } from "./types.js";

type AjvLike = {
  compile(schema: object): ((data: unknown) => boolean) & { errors?: ErrorObject[] | null };
};

const Ajv2020 = Ajv2020Module.default as unknown as new (opts?: { allErrors?: boolean; strict?: boolean }) => AjvLike;
const addFormats = addFormatsModule.default as unknown as (ajv: AjvLike) => unknown;

export interface RecordValidationError {
  sourcePath: string;
  errors: ErrorObject[];
}

export interface ValidateRecordsResult {
  valid: SourceRecord[];
  errors: RecordValidationError[];
}

function customError(instancePath: string, message: string): ErrorObject {
  return {
    instancePath,
    schemaPath: "#/x-bgs-kb-integrity",
    keyword: "x-bgs-kb-integrity",
    params: {},
    message,
  };
}

export function findRepoRoot(startPath: string): string | null {
  let current = startPath;
  for (let i = 0; i <= 5; i += 1) {
    if (existsSync(join(current, ".git"))) return current;
    const parent = dirname(current);
    if (parent === current) return null;
    current = parent;
  }
  return null;
}

export function defaultSchemaPathForPack(packRoot: string): string {
  const repoRoot = findRepoRoot(packRoot);
  if (!repoRoot) {
    throw new Error(`Could not locate repo root from pack root '${packRoot}' while resolving record.schema.json`);
  }
  return join(repoRoot, "knowledge", "bgs-kb", "schema", "record.schema.json");
}

function expectedIdFromSourcePath(sourcePath: string): string {
  const withoutPrefix = sourcePath.startsWith("records/") ? sourcePath.slice("records/".length) : sourcePath;
  const withoutExtension = withoutPrefix.endsWith(".md") ? withoutPrefix.slice(0, -".md".length) : withoutPrefix;
  return withoutExtension.split("/").join(".");
}

function additionalIntegrityErrors(record: SourceRecord): ErrorObject[] {
  const errors: ErrorObject[] = [];
  const expectedId = expectedIdFromSourcePath(record.sourcePath);
  if (record.id !== expectedId) {
    errors.push(customError("/id", `must match source path stem '${expectedId}'`));
  }
  if (!Array.isArray(record.domains) || record.domains.length === 0) {
    errors.push(customError("/domains", "must contain at least one domain"));
  }
  if (!Array.isArray(record.sources) || record.sources.length === 0) {
    errors.push(customError("/sources", "must contain at least one source"));
  }
  const games = new Set(record.appliesTo?.games ?? []);
  for (const excluded of record.appliesTo?.excludes ?? []) {
    if (games.has(excluded)) {
      errors.push(customError("/appliesTo/excludes", `must not overlap appliesTo.games (${excluded})`));
    }
  }
  return errors;
}

export function validateRecords(records: SourceRecord[], packRoot: string, schemaPath?: string): ValidateRecordsResult {
  const resolvedSchemaPath = schemaPath ?? defaultSchemaPathForPack(packRoot);
  const schema = JSON.parse(readFileSync(resolvedSchemaPath, "utf8")) as object;
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const validate = ajv.compile(schema);

  const errors: RecordValidationError[] = [];
  const valid: SourceRecord[] = [];

  for (const record of records) {
    const { bodyMd: _bodyMd, sourcePath: _sourcePath, ...frontmatter } = record;
    const ok = validate(frontmatter);
    if (!ok) {
      errors.push({ sourcePath: record.sourcePath, errors: [...(validate.errors ?? [])] });
      continue;
    }

    const integrityErrors = additionalIntegrityErrors(record);
    if (integrityErrors.length > 0) {
      errors.push({ sourcePath: record.sourcePath, errors: integrityErrors });
      continue;
    }

    valid.push(record);
  }

  const byId = new Map<string, string[]>();
  for (const record of valid) {
    const paths = byId.get(record.id) ?? [];
    paths.push(record.sourcePath);
    byId.set(record.id, paths);
  }
  for (const [id, paths] of byId) {
    if (paths.length <= 1) continue;
    for (const sourcePath of paths) {
      errors.push({ sourcePath, errors: [customError("/id", `duplicate id '${id}' also appears in ${paths.join(", ")}`)] });
    }
  }

  return errors.length > 0 ? { valid: [], errors } : { valid, errors };
}

export function formatValidationError(sourcePath: string, error: ErrorObject): string {
  const path = error.instancePath || "/";
  const message = error.message ?? "validation failed";
  return `${sourcePath}: ${path}: ${message}`;
}
