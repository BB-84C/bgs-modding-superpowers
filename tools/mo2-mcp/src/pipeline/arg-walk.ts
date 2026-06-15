/** Recursive argument walkers shared by pipeline safety rules. */

export interface StringArg {
  key: string;
  path: string;
  value: string;
}

export function* walkStringArgs(
  value: unknown,
  path = "args",
  key = "",
): Generator<StringArg> {
  if (typeof value === "string") {
    yield { key, path, value };
    return;
  }

  if (value === null || typeof value !== "object") return;

  if (Array.isArray(value)) {
    for (const [index, child] of value.entries()) {
      yield* walkStringArgs(child, `${path}[${index}]`, String(index));
    }
    return;
  }

  for (const [childKey, child] of Object.entries(value as Record<string, unknown>)) {
    yield* walkStringArgs(child, `${path}.${childKey}`, childKey);
  }
}
