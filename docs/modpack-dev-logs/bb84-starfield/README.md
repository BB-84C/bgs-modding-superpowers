# BB84 Starfield Modpack — Plugin Substrate Mirror

This directory mirrors `D:\Starfield MO2\docs\` from BB84's real-world Starfield
modpack (`BB84自用2` profile) as substrate examples for the
`bgs-modding-superpowers` plugin.

**Purpose**: provide a concrete, real-modpack example of how the
`writing-modpack-devlog` and `writing-modpack-changelog` skills produce
substrate, and how the `evaluating-bgs-mods` / `curating-bgs-modpack` /
`diagnosing-bgs-problems` / `testing-bgs-modpack` skills' "Senior Curator's
Lens" sections look when applied by a real curator.

**Source of truth**: `D:\Starfield MO2\docs\` is authoritative. This mirror
is a snapshot for plugin substrate. Updates here happen by manual sync after
real-modpack changes; the mirror is **not** a live link.

**Substrate scope**:
- `dev-log.md` — mirror of real audit log
- `release-changelog.md` — mirror of real release history scaffold

**Not in mirror**: actual modlist / plugins.txt / mod meta.ini files. Those
live in the real MO2 install only; mirroring them would leak the user's
specific load order and inflate this repo.
