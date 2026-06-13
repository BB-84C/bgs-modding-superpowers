"""String table for the MO2 Assets Inspector GUI.

Default locale = zh-Hans (matches the user's reference UX).
Use `get_strings()` for default, or `get_strings(Locale.EN)` to override.
The plugin's mobase `settings()` exposes the locale as a setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Locale(str, Enum):
    ZH_HANS = "zh-Hans"
    EN = "en"


@dataclass(frozen=True)
class Strings:
    locale: Locale
    window_title: str
    refresh_button: str
    section_kept: str
    section_overwritten: str
    section_no_conflict: str
    column_file: str
    column_overrider: str
    column_overridden_by: str
    column_priority: str
    column_mod_name: str
    column_conflict_count: str
    column_file_count: str
    column_archive_type: str
    rationale_header: str
    kb_reference_header: str
    unsupported_game_message: str


_ZH_HANS = Strings(
    locale=Locale.ZH_HANS,
    window_title="BGS 资源审计器",
    refresh_button="刷新",
    section_kept="冲突中被保留的文件",
    section_overwritten="冲突中被覆盖的文件",
    section_no_conflict="下列文件无冲突",
    column_file="文件",
    column_overrider="覆盖文件的来源模组",
    column_overridden_by="被覆盖的模组",
    column_priority="优先级",
    column_mod_name="模组名称",
    column_conflict_count="冲突",
    column_file_count="文件数",
    column_archive_type="来源类型",
    rationale_header="判定依据",
    kb_reference_header="知识库引用",
    unsupported_game_message=(
        "当前游戏暂未在 mo2-assets-engine 的第一阶段覆盖范围内。"
        "支持的游戏：Skyrim 系列 / Fallout 3 / Fallout NV / Fallout 4 / Starfield。"
    ),
)

_EN = Strings(
    locale=Locale.EN,
    window_title="BGS Assets Inspector",
    refresh_button="Refresh",
    section_kept="Files kept (this mod wins)",
    section_overwritten="Files overwritten (this mod loses)",
    section_no_conflict="Files with no conflict",
    column_file="File",
    column_overrider="Overrider (wins this path)",
    column_overridden_by="Overridden by",
    column_priority="Priority",
    column_mod_name="Mod name",
    column_conflict_count="Conflicts",
    column_file_count="Files",
    column_archive_type="Source",
    rationale_header="Resolution rationale",
    kb_reference_header="Knowledge-base references",
    unsupported_game_message=(
        "The active game is not in mo2-assets-engine's Phase 1 coverage. "
        "Supported: Skyrim family / Fallout 3 / Fallout NV / Fallout 4 / Starfield."
    ),
)


_STRINGS_BY_LOCALE: dict[Locale, Strings] = {Locale.ZH_HANS: _ZH_HANS, Locale.EN: _EN}


def get_strings(locale: Locale = Locale.ZH_HANS) -> Strings:
    return _STRINGS_BY_LOCALE[locale]
