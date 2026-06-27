from mo2_assets_engine.conflict_resolver import resolve_tree
from mo2_assets_engine.virtual_data_tree import Provider, SourceType, VirtualDataTree


def _tree(path: str, providers: list[Provider]) -> VirtualDataTree:
    return VirtualDataTree(
        plugins=[],
        archives=[],
        attachments={},
        file_providers={path: providers},
        unattached_archives=[],
        game="fallout4",
    )


def _loose(mod: str, priority: int) -> Provider:
    return Provider(source_mod=mod, source_type=SourceType.LOOSE, mod_priority=priority)


def _archive(mod: str, plugin_order: int, priority: int = 0) -> Provider:
    return Provider(
        source_mod=mod,
        source_type=SourceType.ARCHIVE,
        mod_priority=priority,
        archive_name=f"{mod} - Main.ba2",
        attached_plugin=f"{mod}.esm",
        attached_plugin_load_order=plugin_order,
    )


def test_loose_vs_loose_higher_mod_priority_wins() -> None:
    winners = resolve_tree(_tree("textures/a.dds", [_loose("Low", 1), _loose("High", 9)]))

    resolved = winners["textures/a.dds"]
    assert resolved.winner.source_mod == "High"
    assert [p.source_mod for p in resolved.losers] == ["Low"]
    assert resolved.is_conflict is True


def test_loose_always_wins_over_archive_even_with_lower_mod_priority() -> None:
    winners = resolve_tree(
        _tree("textures/a.dds", [_archive("Packed", plugin_order=99, priority=99), _loose("Loose", 1)])
    )

    assert winners["textures/a.dds"].winner.source_mod == "Loose"


def test_archive_vs_archive_higher_attached_plugin_load_order_wins() -> None:
    winners = resolve_tree(
        _tree("textures/a.dds", [_archive("EarlyPlugin", 1), _archive("LatePlugin", 5)])
    )

    assert winners["textures/a.dds"].winner.source_mod == "LatePlugin"


def test_archive_tie_uses_mod_priority() -> None:
    winners = resolve_tree(
        _tree(
            "textures/a.dds",
            [
                _archive("SamePluginLowMod", plugin_order=3, priority=1),
                _archive("SamePluginHighMod", plugin_order=3, priority=9),
            ],
        )
    )

    assert winners["textures/a.dds"].winner.source_mod == "SamePluginHighMod"


def test_single_provider_is_not_conflict() -> None:
    winners = resolve_tree(_tree("textures/a.dds", [_loose("Only", 0)]))

    assert winners["textures/a.dds"].is_conflict is False
    assert winners["textures/a.dds"].losers == []
