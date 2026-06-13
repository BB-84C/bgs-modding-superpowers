"""Per-bucket explanation + KB record citation.

Bucket -> short human-readable rationale + canonical KB record IDs that
explain the underlying rule. KB record IDs are stable identifiers from
`knowledge/bgs-kb/packs/core/records/archive-precedence/`.

Consumers (CLI, GUI, future MO2 MCP) use this to render "why this verdict"
without re-deriving the engine rules in presentation code.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import ConflictBucket


@dataclass(frozen=True)
class BucketRationale:
    short: str
    kb_record_ids: tuple[str, ...]


_RATIONALES: dict[ConflictBucket, BucketRationale] = {
    ConflictBucket.NO_CONFLICT: BucketRationale(
        short="Only one enabled mod contributes this path; no conflict.",
        kb_record_ids=("archive-precedence.plugin-order-is-not-asset-order.v1",),
    ),
    ConflictBucket.LOOSE_OVERWRITES_LOOSE: BucketRationale(
        short=(
            "Both mods ship this path as a loose file. The mod with the higher "
            "modlist priority wins (= the one closer to the top of modlist.txt)."
        ),
        kb_record_ids=(
            "load-order.mo2-left-pane-vs-right-pane.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
    ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE: BucketRationale(
        short=(
            "This mod ships this path as a loose file, but another loose file "
            "from a higher-priority mod wins. Adjust modlist priority to flip."
        ),
        kb_record_ids=(
            "load-order.mo2-left-pane-vs-right-pane.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
    ConflictBucket.LOOSE_OVERWRITES_ARCHIVE: BucketRationale(
        short=(
            "Loose files ALWAYS win over archived assets, regardless of plugin "
            "or archive load order. The loose copy wins."
        ),
        kb_record_ids=("archive-precedence.loose-over-archive.v1",),
    ),
    ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE: BucketRationale(
        short=(
            "This entry is inside a BSA/BA2 archive, but another mod ships the "
            "same path as a loose file. Loose ALWAYS wins; the archived entry "
            "loses regardless of plugin load order."
        ),
        kb_record_ids=("archive-precedence.loose-over-archive.v1",),
    ),
    ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE: BucketRationale(
        short=(
            "Both contributions come from archives. The archive loaded LATER "
            "wins; archive load order is derived from plugin order in plugins.txt "
            "via naming convention (<base>.bsa or <base> - Main.ba2 etc.)."
        ),
        kb_record_ids=(
            "archive-precedence.bsa-vs-ba2-by-game.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
    ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE: BucketRationale(
        short=(
            "This entry is inside an archive that loses to another archive "
            "loaded later. Move the owning plugin later in plugins.txt to flip."
        ),
        kb_record_ids=(
            "archive-precedence.bsa-vs-ba2-by-game.v1",
            "archive-precedence.plugin-order-is-not-asset-order.v1",
        ),
    ),
}


def rationale_for_bucket(bucket: ConflictBucket) -> BucketRationale:
    return _RATIONALES[bucket]
