from mo2_assets_engine.archive_order import Game, discover_archives_for_plugins


def test_numbered_texture_variants_attach_to_plugin() -> None:
    attachments = discover_archives_for_plugins(
        plugins=["Foo.esm"],
        candidate_archives=[
            "Foo - Textures.ba2",
            "Foo - Textures01.ba2",
            "Foo - Textures02.ba2",
            "Foo - Main01.ba2",
            "Unrelated - Textures01.ba2",
        ],
        game=Game.FALLOUT4,
    )

    assert attachments == {
        "foo - textures.ba2": "Foo.esm",
        "foo - textures01.ba2": "Foo.esm",
        "foo - textures02.ba2": "Foo.esm",
        "foo - main01.ba2": "Foo.esm",
    }


def test_starfield_accepts_no_suffix_ba2() -> None:
    attachments = discover_archives_for_plugins(
        plugins=["StarfieldCommunityPatch.esm"],
        candidate_archives=[
            "StarfieldCommunityPatch.ba2",
            "StarfieldCommunityPatch - Main.ba2",
            "StarfieldCommunityPatch - Textures02.ba2",
        ],
        game=Game.STARFIELD,
    )

    assert attachments == {
        "starfieldcommunitypatch.ba2": "StarfieldCommunityPatch.esm",
        "starfieldcommunitypatch - main.ba2": "StarfieldCommunityPatch.esm",
        "starfieldcommunitypatch - textures02.ba2": "StarfieldCommunityPatch.esm",
    }


def test_skyrim_numbered_texture_bsa_variants_attach() -> None:
    attachments = discover_archives_for_plugins(
        plugins=["Foo.esp"],
        candidate_archives=["Foo.bsa", "Foo - Textures.bsa", "Foo - Textures2.bsa"],
        game=Game.SKYRIM,
    )

    assert attachments == {
        "foo.bsa": "Foo.esp",
        "foo - textures.bsa": "Foo.esp",
        "foo - textures2.bsa": "Foo.esp",
    }


def test_ambiguous_archive_match_is_claimed_by_earliest_plugin() -> None:
    attachments = discover_archives_for_plugins(
        plugins=["Foo.esm", "Foo.esp"],
        candidate_archives=["Foo - Main.ba2"],
        game=Game.FALLOUT4,
    )

    assert attachments == {"foo - main.ba2": "Foo.esm"}
