#!/usr/bin/env bash
# Bump version across all manifests declared in .version-bump.json.
#
# Usage: scripts/bump-version.sh <new-version>
#
# Requires: jq (for JSON path mutation).
#
# Each entry in .version-bump.json has:
#   path  — relative path to the manifest
#   field — dotted JSON path to the version field (e.g. "version", "plugins.0.version")

set -euo pipefail

NEW_VERSION="${1:-}"
if [ -z "$NEW_VERSION" ]; then
  echo "Usage: $0 <new-version>" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required (https://stedolan.github.io/jq/)" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$REPO_ROOT/.version-bump.json"

if [ ! -f "$CONFIG" ]; then
  echo "error: .version-bump.json not found at $CONFIG" >&2
  exit 3
fi

# Convert a dotted field path to a jq setpath array (numeric segments stay numeric).
# Example: "plugins.0.version" -> ["plugins", 0, "version"]
make_jq_path() {
  jq -nc --arg field "$1" '
    $field | split(".") | map(
      if test("^[0-9]+$") then tonumber else . end
    )
  '
}

while IFS= read -r entry; do
  path=$(jq -r '.path' <<<"$entry")
  field=$(jq -r '.field' <<<"$entry")
  full_path="$REPO_ROOT/$path"

  if [ ! -f "$full_path" ]; then
    echo "warn: $path not found, skipping" >&2
    continue
  fi

  jq_path=$(make_jq_path "$field")
  jq --arg v "$NEW_VERSION" --argjson p "$jq_path" \
     'setpath($p; $v)' \
     "$full_path" > "$full_path.tmp" && mv "$full_path.tmp" "$full_path"

  echo "bumped $path :: $field -> $NEW_VERSION"
done < <(jq -c '.files[]' "$CONFIG")

echo
echo "done. Review with: git diff"
echo "Audit (search for unchanged version strings) is the human's responsibility for now."
