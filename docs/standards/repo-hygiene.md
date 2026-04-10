# Repo Hygiene Standard

## Durable Content

Tracked files should contain durable knowledge, workflow definitions, project docs, templates, or tested tooling.

## Ignored Working Content

Raw investigation output belongs in `.artifacts/` and must not be committed.

## Artifact Lifecycle

1. Collect raw material in `.artifacts/investigation/<date-topic>/raw/`.
2. Distill reusable findings into tracked docs.
3. Move still-needed raw material to `.artifacts/archive/<date-topic>/`.
4. Delete archived raw material when it is no longer needed.

## Root Cleanliness

Do not leave temporary files, dumps, screenshots, or local machine state in the repository root.
