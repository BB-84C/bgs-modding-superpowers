# Repo Cleanliness Hook

## Trigger

Before creating, moving, staging, or committing files in this repository.

## Check

Reject raw artifacts, temporary dumps, local machine state, and noisy root-level files.

## Action

Move temporary output into `.artifacts/`, summarize durable findings in tracked docs, and keep the root clean.
