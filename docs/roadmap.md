# Plugin Roadmap

This is a lightweight navigation document for the plugin's current direction. It points to the durable design and implementation docs rather than duplicating them here.

## Now

- Maintain the bootstrap baseline and keep this status view aligned with what is actually scaffolded.
- Use the implementation plan documents in `docs/plans/` for the approved next-phase task sequence.

## Next

- Start the first post-bootstrap implementation phase: flesh out the scaffolded skills, hooks, agents, templates, and tooling specs into working workflows.

## Later

- Add lightweight roadmap updates here as major implementation milestones land.
- Scaffold `save-safety-guard` only when the project is ready for save-risk policy and warning behavior; it is planned later and is not part of the current bootstrap baseline.
- Keep detailed architecture and implementation notes in the existing design and plan documents.

## Blocked / Needs Research

- Verify the exact OpenCode plugin packaging format before adding install or metadata files beyond the current placeholders.
- Verify the safest initial xEdit and integration contracts before turning specs into tooling.

## Done

- Approved the initial architecture and bootstrap plan documented in the existing design and implementation docs.
- Landed the first-wave bootstrap scaffolding: repository structure, baseline standards, skill and hook skeletons, templates, integration placeholders, and bootstrap verification scripts.
