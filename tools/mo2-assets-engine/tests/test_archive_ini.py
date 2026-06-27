from pathlib import Path

from mo2_assets_engine.archive_ini import read_archive_lists


def test_reads_sresource_archive_lists_from_archive_section(tmp_path: Path) -> None:
    ini = tmp_path / "StarfieldCustom.ini"
    ini.write_text(
        "[Archive]\n"
        "sResourceArchive2List=Foo - Main.ba2, Foo - Textures01.ba2\n"
        "sResourceIndexFileList=Foo.ba2\n",
        encoding="utf-8",
    )

    lists = read_archive_lists([ini])

    assert lists.explicit_archives == [
        "Foo - Main.ba2",
        "Foo - Textures01.ba2",
        "Foo.ba2",
    ]


def test_skips_comments_and_unions_multiple_keys_and_files(tmp_path: Path) -> None:
    first = tmp_path / "Fallout4Custom.ini"
    second = tmp_path / "Fallout4.ini"
    first.write_text(
        "; comment\n"
        "[Archive]\n"
        "sResourceArchiveList=Base - Main.ba2\n"
        "# comment\n"
        "sResourceArchiveList2=Base - Textures.ba2\n",
        encoding="utf-8",
    )
    second.write_text(
        "[Archive]\n"
        "sResourceArchive2List=Base - Textures.ba2, Other.ba2\n",
        encoding="utf-8",
    )

    lists = read_archive_lists([first, second])

    assert lists.explicit_archives == [
        "Base - Main.ba2",
        "Base - Textures.ba2",
        "Other.ba2",
    ]


def test_missing_or_archive_less_ini_returns_empty(tmp_path: Path) -> None:
    ini = tmp_path / "SkyrimCustom.ini"
    ini.write_text("[General]\nfoo=bar\n", encoding="utf-8")

    lists = read_archive_lists([tmp_path / "missing.ini", ini])


    assert lists.explicit_archives == []
