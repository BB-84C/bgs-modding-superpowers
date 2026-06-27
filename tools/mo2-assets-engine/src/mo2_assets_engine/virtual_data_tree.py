"""Build the unified virtual Data tree seen by the game runtime."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from .archive_ini import IniArchiveLists
from .archive_order import Game, discover_archives_for_plugins
from .mod_enumerator import enumerate_projected_loose_paths
from .profile import MO2Profile


class SourceType(StrEnum):
    LOOSE = "loose"
    ARCHIVE = "archive"


@dataclass(frozen=True)
class Plugin:
    name: str
    source_mod: str
    mod_priority: int
    load_order: int


@dataclass(frozen=True)
class Archive:
    name: str
    source_mod: str
    mod_priority: int


@dataclass(frozen=True)
class Provider:
    """A single mod's contribution to one virtual Data path."""

    source_mod: str
    source_type: SourceType
    mod_priority: int
    archive_name: str | None = None
    attached_plugin: str | None = None
    attached_plugin_load_order: int | None = None


@dataclass(frozen=True)
class UnattachedArchive:
    name: str
    source_mod: str
    reason: str


@dataclass(frozen=True)
class VirtualDataTree:
    plugins: list[Plugin] = field(default_factory=list)
    archives: list[Archive] = field(default_factory=list)
    attachments: dict[str, str] = field(default_factory=dict)
    file_providers: dict[str, list[Provider]] = field(default_factory=dict)
    unattached_archives: list[UnattachedArchive] = field(default_factory=list)
    game: str = ""


def build_virtual_data_tree(
    *,
    profile: MO2Profile,
    game: Game | str | None,
    ini_archive_lists: IniArchiveLists | None = None,
) -> VirtualDataTree:
    engine_game = Game(game) if game is not None else None
    plugins = _build_plugin_pool(profile)
    archives = _build_archive_pool(profile)

    attachments = (
        discover_archives_for_plugins(
            plugins=[plugin.name for plugin in sorted(plugins, key=lambda plugin: plugin.load_order)],
            candidate_archives=[archive.name for archive in archives],
            game=engine_game,
        )
        if engine_game is not None
        else {}
    )
    plugin_by_name = {plugin.name.lower(): plugin for plugin in plugins}
    ini_claimed = {
        archive_name.lower()
        for archive_name in (ini_archive_lists.explicit_archives if ini_archive_lists else [])
    }

    # Build file providers from PROJECTED LOOSE PATHS only.
    #
    # Archive contents are NOT enumerated. `.ba2`/`.bsa` files at the mod-root
    # are projected by `enumerate_projected_loose_paths` as ordinary files
    # (path = `<archive_name>.{ba2,bsa}`), which gives clean file-to-file
    # conflict detection when two mods ship the same archive name without
    # requiring archive format parsing.
    #
    # The Plugin/Archive metadata above and `attachments` map remain populated
    # for future re-expansion (member-level enumeration was previously here and
    # may return when the engine's BA2 reader covers Starfield v3+ etc.), but
    # no archive-source providers are produced today.
    file_providers: dict[str, list[Provider]] = defaultdict(list)
    for mod in profile.enabled_mods:
        for relative_path in enumerate_projected_loose_paths(mod):
            file_providers[relative_path].append(
                Provider(
                    source_mod=mod.name,
                    source_type=SourceType.LOOSE,
                    mod_priority=mod.priority,
                )
            )

    # `plugin_by_name` is no longer consumed in this function (was used by the
    # removed archive-member loop). Kept built above because future re-expansion
    # will need it; suppress the unused-variable signal.
    _ = plugin_by_name

    unattached = [
        UnattachedArchive(
            name=archive.name,
            source_mod=archive.source_mod,
            reason="no_matching_plugin",
        )
        for archive in archives
        if archive.name.lower() not in attachments and archive.name.lower() not in ini_claimed
    ]

    return VirtualDataTree(
        plugins=plugins,
        archives=archives,
        attachments=attachments,
        file_providers=dict(file_providers),
        unattached_archives=unattached,
        game=engine_game.value if engine_game is not None else "unmodeled",
    )


def _build_plugin_pool(profile: MO2Profile) -> list[Plugin]:
    load_order_by_plugin = {name.lower(): index for index, name in enumerate(profile.enabled_plugins)}
    winning_by_name: dict[str, Plugin] = {}
    for mod in sorted(profile.enabled_mods, key=lambda item: item.priority):
        if not mod.root.exists():
            continue
        for child in sorted(mod.root.iterdir()):
            if not child.is_file() or child.suffix.lower() not in (".esp", ".esm", ".esl"):
                continue
            plugin_key = child.name.lower()
            load_order = load_order_by_plugin.get(plugin_key)
            if load_order is None:
                continue
            winning_by_name[plugin_key] = Plugin(
                name=child.name,
                source_mod=mod.name,
                mod_priority=mod.priority,
                load_order=load_order,
            )
    return sorted(winning_by_name.values(), key=lambda plugin: plugin.load_order)


def _build_archive_pool(profile: MO2Profile) -> list[Archive]:
    winning_by_name: dict[str, Archive] = {}
    for mod in sorted(profile.enabled_mods, key=lambda item: item.priority):
        if not mod.root.exists():
            continue
        for child in sorted(mod.root.iterdir()):
            if not child.is_file() or child.suffix.lower() not in (".ba2", ".bsa"):
                continue
            winning_by_name[child.name.lower()] = Archive(
                name=child.name,
                source_mod=mod.name,
                mod_priority=mod.priority,
            )
    return sorted(winning_by_name.values(), key=lambda archive: archive.name.lower())
