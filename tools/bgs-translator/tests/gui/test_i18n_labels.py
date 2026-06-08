"""GUI i18n label polish tests."""

from __future__ import annotations


def test_zh_cn_profiles_nav_label_has_provider_context() -> None:
    from bgs_translator.gui.i18n import Translator

    translator = Translator("zh-cn")

    assert translator.gettext("Profiles") == "大语言模型提供商档案列表"
    assert translator.gettext("Profile") == "档案"
    assert translator.gettext("Add new provider profile") == "新增提供商档案"
