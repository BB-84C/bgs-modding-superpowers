"""6-bucket loose-vs-archive conflict resolver.

Mirrors MO2's `ModInfoWithConflictInfo::doConflictCheck()`
(see src/modinfowithconflictinfo.cpp in modorganizer2/modorganizer).

Rules:
    1. Both loose          -> modlist priority decides (higher wins).
    2. Loose vs archive    -> loose ALWAYS wins.
    3. Both archive        -> archive load_order decides (higher wins).
    4. Single entry        -> NO_CONFLICT.

Per-path output is a `ResolvedWinner`. Per-mod output is a `ConflictReport`
with `kept` / `overwritten` / `no_conflict` lists mirroring MO2's UI.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .types import (
    ConflictBucket,
    ConflictReport,
    FileEntry,
    FileEntryKind,
    Mod,
    ResolvedWinner,
)


def resolve_all_winners(
    *,
    mods: list[Mod],
    entries_by_mod: dict[str, list[FileEntry]],
) -> dict[str, ResolvedWinner]:
    priority_by_mod = {m.name: m.priority for m in mods}
    by_path: dict[str, list[FileEntry]] = defaultdict(list)
    for entries in entries_by_mod.values():
        for entry in entries:
            by_path[entry.relative_path].append(entry)

    winners: dict[str, ResolvedWinner] = {}
    for path, entries in by_path.items():
        if len(entries) == 1:
            winners[path] = ResolvedWinner(
                relative_path=path,
                winner=entries[0],
                losers=[],
                bucket=ConflictBucket.NO_CONFLICT,
            )
            continue
        winner, losers, bucket = _decide_winner(entries, priority_by_mod)
        winners[path] = ResolvedWinner(
            relative_path=path, winner=winner, losers=losers, bucket=bucket
        )
    return winners


def _decide_winner(
    entries: list[FileEntry],
    priority_by_mod: dict[str, int],
) -> tuple[FileEntry, list[FileEntry], ConflictBucket]:
    loose = [e for e in entries if e.kind is FileEntryKind.LOOSE]
    archived = [e for e in entries if e.kind is FileEntryKind.ARCHIVED]

    if loose and archived:
        # Rule 2: loose ALWAYS wins.
        if len(loose) == 1:
            winner = loose[0]
            losers = archived
            return winner, losers, ConflictBucket.LOOSE_OVERWRITES_ARCHIVE
        # Multiple loose + at least one archive: highest-priority loose wins.
        winner = max(loose, key=lambda e: priority_by_mod.get(e.owner_mod, -1))
        losers = [e for e in entries if e is not winner]
        return winner, losers, ConflictBucket.LOOSE_OVERWRITES_LOOSE

    if loose:
        # Rule 1: highest modlist priority among loose entries.
        winner = max(loose, key=lambda e: priority_by_mod.get(e.owner_mod, -1))
        losers = [e for e in loose if e is not winner]
        return winner, losers, ConflictBucket.LOOSE_OVERWRITES_LOOSE

    # Rule 3: archive-vs-archive. Highest load_order wins.
    def _load_order_of(entry: FileEntry) -> int:
        assert entry.archive is not None
        return entry.archive.load_order

    winner = max(archived, key=_load_order_of)
    losers = [e for e in archived if e is not winner]
    return winner, losers, ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE


@dataclass
class ConflictResolver:
    """Bundles winner computation + per-mod report building."""

    mods: list[Mod]
    entries_by_mod: dict[str, list[FileEntry]]

    def __post_init__(self) -> None:
        self._winners = resolve_all_winners(mods=self.mods, entries_by_mod=self.entries_by_mod)
        self._mods_by_name = {m.name: m for m in self.mods}

    def report_for_mod(self, mod_name: str) -> ConflictReport:
        mod = self._mods_by_name[mod_name]
        kept: list[ResolvedWinner] = []
        overwritten: list[ResolvedWinner] = []
        no_conflict: list[FileEntry] = []
        for entry in self.entries_by_mod.get(mod_name, []):
            winner = self._winners[entry.relative_path]
            if winner.bucket is ConflictBucket.NO_CONFLICT:
                no_conflict.append(entry)
            elif winner.winner.owner_mod == mod_name:
                kept.append(winner)
            else:
                # This mod's entry is among the losers. Re-bucket from the
                # losing mod's perspective.
                overwritten.append(_flip_bucket_perspective(winner))
        return ConflictReport(
            mod=mod,
            kept=kept,
            overwritten=overwritten,
            no_conflict=no_conflict,
        )


def _flip_bucket_perspective(winner: ResolvedWinner) -> ResolvedWinner:
    flipped = {
        ConflictBucket.LOOSE_OVERWRITES_LOOSE: ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.LOOSE_OVERWRITES_ARCHIVE: ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE: ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE,
    }
    return ResolvedWinner(
        relative_path=winner.relative_path,
        winner=winner.winner,
        losers=winner.losers,
        bucket=flipped[winner.bucket],
    )
