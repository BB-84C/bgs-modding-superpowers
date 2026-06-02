# Community API Reconnaissance

Date: 2026-05-14  
Status: preliminary reconnaissance only; no implementation approved  
Scope: FKMods forum access, Nexus Mods read/upload/community surfaces  

## Purpose

Preserve the initial reconnaissance work around community-facing automation before the project decides whether to build any related capability.

This document is intentionally a research note, not an implementation plan. The current project decision is to **defer** this work and avoid losing the findings.

## Current decision

- Do **not** implement community-posting or community-upload workflows yet.
- If this area is revisited later, prefer stable official HTTP APIs.
- Do **not** treat browser automation / Playwright / MCP interaction as the preferred runtime path.
- Use browser tooling only for reconnaissance or debugging, not as the default product seam.

## Executive summary

### FKMods

- FKMods exposes a readable forum API surface consistent with a Flarum JSON:API deployment.
- Anonymous read access appears viable for discussion discovery and thread retrieval.
- Posting is not a good default automation target: it is account-gated, includes anti-bot protections, and the site's `robots.txt` explicitly disallows `/api` crawling.
- Practical recommendation: if FKMods is ever integrated, treat it as a **read-only research source**.

### Nexus Mods

- Nexus Mods has real official APIs for metadata and some authenticated user workflows.
- Nexus also now has an official v3 upload API for **existing mod file groups**, but it is still marked evaluation/beta and does not remove the need for an already-created mod page.
- This reconnaissance did **not** confirm a stable public API for forum posting, creating new mod pages, or broad community-forum browsing/posting workflows.
- Nexus ToS and AUP materially raise the risk of browser-driven scraping or posting automation.
- Practical recommendation: if Nexus is ever integrated, restrict it to **officially supported read APIs** and possibly **existing-mod version uploads**.

## Evidence posture and caveats

- This reconnaissance used read-only inspection and public documentation.
- No account creation, posting, replying, uploading, or other state-changing action was performed.
- Conclusions about write paths are therefore limited to public docs, public schema/documentation surfaces, and platform-identity inference.
- Any future write-capable integration must be re-validated against the live site at implementation time.

## FKMods findings

### Platform shape

Observed behavior is consistent with a Flarum forum instance exposing the standard JSON:API surface.

Notable evidence captured during reconnaissance:

- `https://fkmods.com/api` returns `application/vnd.api+json`
- `https://fkmods.com/api/discussions` returns discussion data anonymously
- API root fields include forum-level capability and signup metadata
- `robots.txt` includes `Disallow: /api`

Relevant forum/API indicators observed:

- `apiUrl: https://fkmods.com/api`
- `baseUrl: https://fkmods.com`
- `canViewForum: true`
- `allowSignUp: true`
- `canStartDiscussion: false` for the anonymous caller
- `postWithoutHCaptcha: false`

### FKMods capability assessment

| Capability | Recon result | Notes |
| --- | --- | --- |
| Read discussion lists | Likely supported | Anonymous `/api/discussions` access observed |
| Read thread content | Likely supported | Consistent with exposed Flarum discussion/post API shape |
| Search / index for research | Plausible | Should still be treated politely and rate-limited |
| Autonomous posting/replying | Not recommended | Account-gated, anti-bot friction, social/moderation risk |
| Browser/MCP fallback | Not recommended | API-first directive is cleaner, and posting should not be automated by default |

### FKMods recommendation

If the project ever integrates FKMods, the safest and most defensible product seam is:

- read-only ingestion
- low-rate polling or on-demand fetch
- local indexing / retrieval for research assistance
- explicit refusal to autonomously post or reply

Even if Flarum write endpoints are technically available after authentication, that is not enough to justify making posting an agent default. The policy and community-fit risks are higher than the engineering upside.

## Nexus Mods findings

### Official API surfaces observed

### V1 REST

Stable read-oriented surface for mod/game/file metadata and some authenticated user actions.

Typical fit:

- game and mod metadata
- file lists and file details
- changelogs
- trending/latest/updated mod discovery
- some user-scoped actions such as endorsements/tracking

### V2 GraphQL

Publicly documented, but explicitly described by Nexus as work in progress.

Observed value:

- richer query surface than v1 in some domains
- broader typed object graph
- some authenticated flows exist

Important caution:

- the public documentation explicitly warns that structures and behaviors may change
- comment-thread-related types and fields are visible in the docs, but this reconnaissance did **not** confirm a stable, supported public community-posting workflow from that alone

### V3 Upload API

Official upload/update surface exists and is used by Nexus' public GitHub upload action, but the current documented use is oriented around updating files for an **existing** mod/file-group context.

Important limitation observed:

- it requires a `file_group_id`
- obtaining that presupposes an already-created mod page and an initial file context
- therefore this is not equivalent to a full "create a brand-new mod page from nothing" API

### Nexus capability assessment

| Capability | Recon result | Notes |
| --- | --- | --- |
| Read mod metadata | Supported | Strong fit for official API usage |
| Read file metadata | Supported | Strong fit for official API usage |
| Download/workflow plumbing | Partially supported | Depends on user/account context and official rules |
| Upload a new file version to an existing mod | Plausibly supported | Official v3 upload path exists, still evaluation/beta |
| Create a brand-new mod page | Not confirmed / likely unsupported in public API | Would need fresh validation if ever required |
| Forum browsing/posting | Not confirmed as a safe official API path | Do not assume support |
| Browser/MCP automation to fill API gaps | Not recommended | ToS/AUP risk is too high |

### Nexus policy constraints

This reconnaissance found two policy constraints that matter more than mere technical possibility:

1. **API Acceptable Use Policy**
   - public-facing apps should use the sanctioned API/app-registration path
   - mass scraping / rehosting behavior is disallowed
   - request identity must be honest and explicit

2. **Terms of Service**
   - explicit anti-scraping / anti-bot / anti-text-and-data-mining language exists
   - AI-training / fine-tuning / validation use is explicitly restricted
   - this makes unofficial browser automation a poor foundation for product capability

### Nexus recommendation

If the project ever integrates Nexus Mods, keep the scope narrow:

- official metadata reads via sanctioned API surfaces
- possibly existing-mod upload/version update workflows via the official upload API
- no forum scraping
- no forum posting automation
- no browser-driven substitution for unsupported capabilities unless Nexus explicitly documents and permits it

## Recommended future capability boundary

If this work is revisited later, the likely safe decomposition is:

1. `fkmods-readonly-research`
   - thread discovery
   - thread retrieval
   - local knowledge indexing

2. `nexus-readonly-metadata`
   - mod metadata
   - file metadata
   - changelog/update discovery

3. `nexus-existing-mod-upload`
   - only for updating already-established mod/file groups
   - only after re-validating the live v3 contract and policy posture

Capabilities that should remain out of scope unless the external policy picture changes:

- FKMods autonomous posting/replying
- Nexus forum posting
- Nexus forum scraping
- Nexus new-mod-page creation via browser automation
- any MCP/Playwright runtime path used only to work around a missing official API

## Open questions if this area is revisited

1. FKMods write path
   - how much signup friction exists in practice?
   - is there moderation or approval for new users?
   - would the site operator even want automated research traffic?

2. Nexus upload path
   - what does the current v3 contract look like at implementation time?
   - is upload still evaluation-only?
   - has Nexus added first-class mod-page creation support?

3. Nexus community interactions
   - are comment-creation/community endpoints officially documented by then?
   - what exact usage would their support team approve for an AI-assisted modding tool?

## Deferred conclusion

The reconnaissance does not justify building community-posting automation now.

The strongest future candidates are:

- FKMods as a read-only research source
- Nexus as an official metadata source
- Nexus existing-mod upload/update workflows only if and when the official contract is still present and acceptable

Everything else in this area should remain deferred until the project has a stronger product need and a cleaner policy story.

## Sources consulted during reconnaissance

- FKMods public API root and discussion endpoints
- FKMods `robots.txt`
- Nexus Mods public GraphQL documentation
- Nexus Mods API Acceptable Use Policy
- Nexus Mods Terms of Service
- Nexus Mods public upload-action repository / README
