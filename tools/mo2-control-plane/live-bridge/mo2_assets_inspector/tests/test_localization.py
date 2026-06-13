import pytest

from Mo2AssetsInspector.localization import Locale, get_strings


def test_default_locale_is_zh_hans() -> None:
    strings = get_strings()
    assert strings.locale is Locale.ZH_HANS
    assert strings.window_title  # non-empty


def test_can_get_en_strings() -> None:
    strings = get_strings(Locale.EN)
    assert strings.locale is Locale.EN
    assert strings.window_title


@pytest.mark.parametrize("locale", list(Locale))
def test_every_locale_provides_full_string_set(locale: Locale) -> None:
    strings = get_strings(locale)
    required_attrs = [
        "window_title",
        "refresh_button",
        "section_kept",
        "section_overwritten",
        "section_no_conflict",
        "column_file",
        "column_overrider",
        "column_overridden_by",
        "column_priority",
        "column_mod_name",
        "column_conflict_count",
        "column_file_count",
        "column_archive_type",
        "rationale_header",
        "kb_reference_header",
        "unsupported_game_message",
    ]
    for attr in required_attrs:
        value = getattr(strings, attr)
        assert isinstance(value, str)
        assert value, f"Locale {locale} missing string for {attr}"
