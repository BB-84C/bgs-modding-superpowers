from pathlib import Path

from mo2_assets_engine.conflict_resolver import (
    ConflictResolver,
    resolve_all_winners,
)
from mo2_assets_engine.types import (
    ArchiveEntry,
    ArchiveKind,
    ConflictBucket,
    FileEntry,
    FileEntryKind,
    Mod,
)


def _loose(path: str, owner: str) -> FileEntry:
    return FileEntry(relative_path=path, kind=FileEntryKind.LOOSE, owner_mod=owner, archive=None)


def _archived(path: str, owner: str, archive_name: str, load_order: int) -> FileEntry:
    return FileEntry(
        relative_path=path,
        kind=FileEntryKind.ARCHIVED,
        owner_mod=owner,
        archive=ArchiveEntry(name=archive_name, kind=ArchiveKind.BA2_GENERAL, load_order=load_order),
    )


def test_loose_vs_loose_higher_priority_wins() -> None:
    mods = [
        Mod(name="HighPrio", priority=10, enabled=True, root=Path("/x/HighPrio")),
        Mod(name="LowPrio", priority=5, enabled=True, root=Path("/x/LowPrio")),
    ]
    entries_by_mod = {
        "HighPrio": [_loose("a.dds", "HighPrio")],
        "LowPrio": [_loose("a.dds", "LowPrio")],
    }
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    assert len(winners) == 1
    winner = winners["a.dds"]
    assert winner.winner.owner_mod == "HighPrio"
    assert winner.bucket is ConflictBucket.LOOSE_OVERWRITES_LOOSE
    assert [loser.owner_mod for loser in winner.losers] == ["LowPrio"]


def test_loose_always_wins_over_archive() -> None:
    mods = [
        Mod(name="LowPrioLoose", priority=1, enabled=True, root=Path("/x/LowPrioLoose")),
        Mod(name="HighPrioArchive", priority=100, enabled=True, root=Path("/x/HighPrioArchive")),
    ]
    entries_by_mod = {
        "LowPrioLoose": [_loose("a.dds", "LowPrioLoose")],
        "HighPrioArchive": [_archived("a.dds", "HighPrioArchive", "Foo - Main.ba2", 99)],
    }
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    winner = winners["a.dds"]
    assert winner.winner.owner_mod == "LowPrioLoose"
    assert winner.bucket is ConflictBucket.LOOSE_OVERWRITES_ARCHIVE


def test_archive_vs_archive_higher_load_order_wins() -> None:
    mods = [
        Mod(name="ArchiveA", priority=1, enabled=True, root=Path("/x/ArchiveA")),
        Mod(name="ArchiveB", priority=2, enabled=True, root=Path("/x/ArchiveB")),
    ]
    entries_by_mod = {
        "ArchiveA": [_archived("a.dds", "ArchiveA", "A - Main.ba2", 0)],
        "ArchiveB": [_archived("a.dds", "ArchiveB", "B - Main.ba2", 5)],
    }
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    winner = winners["a.dds"]
    assert winner.winner.owner_mod == "ArchiveB"
    assert winner.bucket is ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE


def test_no_conflict_when_only_one_entry() -> None:
    mods = [Mod(name="Only", priority=1, enabled=True, root=Path("/x/Only"))]
    entries_by_mod = {"Only": [_loose("a.dds", "Only")]}
    winners = resolve_all_winners(mods=mods, entries_by_mod=entries_by_mod)
    assert winners["a.dds"].bucket is ConflictBucket.NO_CONFLICT


def test_build_conflict_report_mirrors_mo2_three_sections() -> None:
    mods = [
        Mod(name="A", priority=2, enabled=True, root=Path("/x/A")),  # winner
        Mod(name="B", priority=1, enabled=True, root=Path("/x/B")),  # loser
    ]
    entries_by_mod = {
        "A": [_loose("contested.dds", "A"), _loose("solo-a.dds", "A")],
        "B": [_loose("contested.dds", "B"), _loose("solo-b.dds", "B")],
    }
    resolver = ConflictResolver(mods=mods, entries_by_mod=entries_by_mod)
    report_a = resolver.report_for_mod("A")

    assert len(report_a.kept) == 1
    assert report_a.kept[0].relative_path == "contested.dds"
    assert report_a.kept[0].bucket is ConflictBucket.LOOSE_OVERWRITES_LOOSE
    assert len(report_a.overwritten) == 0
    assert [e.relative_path for e in report_a.no_conflict] == ["solo-a.dds"]

    report_b = resolver.report_for_mod("B")
    assert len(report_b.overwritten) == 1
    assert report_b.overwritten[0].relative_path == "contested.dds"
    assert report_b.overwritten[0].bucket is ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE
    assert [e.relative_path for e in report_b.no_conflict] == ["solo-b.dds"]
