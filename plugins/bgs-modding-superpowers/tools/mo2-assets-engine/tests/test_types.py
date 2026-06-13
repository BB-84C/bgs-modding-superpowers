from pathlib import Path

from mo2_assets_engine.types import (
    ArchiveEntry,
    ArchiveKind,
    ConflictBucket,
    FileEntry,
    FileEntryKind,
    Mod,
    ResolvedWinner,
)


def test_mod_dataclass_basic_construction() -> None:
    mod = Mod(name="ExampleMod", priority=10, enabled=True, root=Path("/tmp/mods/Example"))
    assert mod.name == "ExampleMod"
    assert mod.priority == 10
    assert mod.enabled is True


def test_file_entry_kinds_cover_loose_and_archive() -> None:
    loose = FileEntry(
        relative_path="textures/foo.dds",
        kind=FileEntryKind.LOOSE,
        owner_mod="ExampleMod",
        archive=None,
    )
    archived = FileEntry(
        relative_path="textures/foo.dds",
        kind=FileEntryKind.ARCHIVED,
        owner_mod="ExampleMod",
        archive=ArchiveEntry(
            name="Example - Main.ba2",
            kind=ArchiveKind.BA2_GENERAL,
            load_order=3,
        ),
    )
    assert loose.kind is FileEntryKind.LOOSE
    assert archived.archive is not None
    assert archived.archive.load_order == 3


def test_conflict_bucket_enum_complete() -> None:
    assert ConflictBucket.NO_CONFLICT.value == "no-conflict"
    assert ConflictBucket.LOOSE_OVERWRITES_LOOSE.value == "loose-overwrites-loose"
    assert ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE.value == "loose-overwritten-by-loose"
    assert ConflictBucket.LOOSE_OVERWRITES_ARCHIVE.value == "loose-overwrites-archive"
    assert ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE.value == "archive-overwritten-by-loose"
    assert ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE.value == "archive-overwrites-archive"
    assert ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE.value == "archive-overwritten-by-archive"


def test_resolved_winner_carries_full_origin_chain() -> None:
    winner = ResolvedWinner(
        relative_path="textures/foo.dds",
        winner=FileEntry(
            relative_path="textures/foo.dds",
            kind=FileEntryKind.LOOSE,
            owner_mod="LooseWinner",
            archive=None,
        ),
        losers=[],
        bucket=ConflictBucket.NO_CONFLICT,
    )
    assert winner.winner.owner_mod == "LooseWinner"
    assert winner.bucket is ConflictBucket.NO_CONFLICT
