from mo2_assets_engine.archive_order import Game, discover_archives_for_plugins


def test_skyrim_archive_naming_convention() -> None:
    order = discover_archives_for_plugins(
        plugins=["Skyrim.esm", "Foo.esp", "Bar.esp"],
        candidate_archives=[
            "Skyrim.bsa",
            "Skyrim - Textures.bsa",
            "Foo.bsa",
            "Bar.bsa",
            "Bar - Textures.bsa",
            "Unrelated.bsa",
        ],
        game=Game.SKYRIM,
    )
    # plugins.txt order = Skyrim, Foo, Bar; Bar loaded last -> wins.
    # Per plugin: main first, textures second.
    assert order.ordered_archives == [
        "Skyrim.bsa",
        "Skyrim - Textures.bsa",
        "Foo.bsa",
        "Bar.bsa",
        "Bar - Textures.bsa",
    ]
    assert order.unattached_archives == ["Unrelated.bsa"]


def test_fo4_archive_naming_convention() -> None:
    order = discover_archives_for_plugins(
        plugins=["Fallout4.esm", "MyMod.esp"],
        candidate_archives=[
            "Fallout4 - Main.ba2",
            "Fallout4 - Textures.ba2",
            "MyMod - Main.ba2",
            "MyMod - Textures.ba2",
            "Orphan - Main.ba2",
        ],
        game=Game.FALLOUT4,
    )
    assert order.ordered_archives == [
        "Fallout4 - Main.ba2",
        "Fallout4 - Textures.ba2",
        "MyMod - Main.ba2",
        "MyMod - Textures.ba2",
    ]
    assert order.unattached_archives == ["Orphan - Main.ba2"]


def test_starfield_uses_ba2() -> None:
    order = discover_archives_for_plugins(
        plugins=["Starfield.esm", "MyOutpost.esp"],
        candidate_archives=[
            "Starfield - Localization.ba2",
            "MyOutpost - Main.ba2",
            "MyOutpost - Textures.ba2",
        ],
        game=Game.STARFIELD,
    )
    assert "MyOutpost - Main.ba2" in order.ordered_archives
    assert "MyOutpost - Textures.ba2" in order.ordered_archives
    assert "Starfield - Localization.ba2" in order.unattached_archives


def test_load_order_rank_lookup() -> None:
    order = discover_archives_for_plugins(
        plugins=["A.esp", "B.esp"],
        candidate_archives=["A.bsa", "B.bsa", "B - Textures.bsa"],
        game=Game.SKYRIM,
    )
    assert order.rank_of("A.bsa") == 0
    assert order.rank_of("B.bsa") == 1
    assert order.rank_of("B - Textures.bsa") == 2
    assert order.rank_of("Nope.bsa") is None
