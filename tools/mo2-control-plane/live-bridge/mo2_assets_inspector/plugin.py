"""IPluginTool implementation for the BGS Assets Inspector.

Lifecycle (per https://www.modorganizer.org/python-plugins-doc/):
    1. MO2 imports the plugin module and calls `createPlugin()`.
    2. MO2 calls `init(organizer)` once with the live IOrganizer instance.
    3. When the user clicks the Tools menu entry, MO2 calls `display()`.
    4. `setParentWidget()` is called before `display()` with MO2's main window.

The window is lazily constructed on first `display()` and reused thereafter.
"""

from __future__ import annotations

import mobase  # type: ignore[import-not-found]  # provided by MO2 runtime
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QWidget

from .bridge import UnsupportedGameError, bundle_paths_from_organizer
from .localization import Locale, get_strings


class BgsAssetsInspectorPlugin(mobase.IPluginTool):
    NAME = "BgsAssetsInspector"
    VERSION = mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.PRE_ALPHA)
    AUTHOR = "BB-84C"
    DESCRIPTION = (
        "Inspect loose-file + BA2/BSA archive conflicts across the active modlist "
        "with the same logic MO2's internal Conflicts tab uses, extended to cover "
        "archive contents."
    )

    def __init__(self) -> None:
        super().__init__()
        self._organizer: mobase.IOrganizer | None = None
        self._parent_widget: QWidget | None = None
        self._main_window: QWidget | None = None

    # --- IPlugin (base) -------------------------------------------------------

    def name(self) -> str:
        return self.NAME

    def author(self) -> str:
        return self.AUTHOR

    def description(self) -> str:
        return self.DESCRIPTION

    def version(self) -> mobase.VersionInfo:
        return self.VERSION

    def isActive(self) -> bool:
        if self._organizer is None:
            return False
        return bool(self._organizer.pluginSetting(self.NAME, "enabled"))

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "enabled",
                "Enable the BGS Assets Inspector tool.",
                True,
            ),
            mobase.PluginSetting(
                "locale",
                "UI locale (one of: zh-Hans, en).",
                Locale.ZH_HANS.value,
            ),
        ]

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    # --- IPluginTool ----------------------------------------------------------

    def displayName(self) -> str:
        strings = get_strings(self._locale())
        return strings.window_title

    def tooltip(self) -> str:
        return self.DESCRIPTION

    def icon(self) -> QIcon:
        return QIcon()  # placeholder; an asset icon can be added later

    def setParentWidget(self, widget: QWidget) -> None:
        self._parent_widget = widget

    def display(self) -> None:
        if self._organizer is None:
            return
        try:
            paths = bundle_paths_from_organizer(self._organizer)
        except UnsupportedGameError as exc:
            strings = get_strings(self._locale())
            QMessageBox.warning(
                self._parent_widget,
                strings.window_title,
                f"{strings.unsupported_game_message}\n\n[{exc}]",
            )
            return

        # Lazy import: the window depends on engine + Qt and we want fast plugin
        # startup. Importing here also lets us reload edits via MO2 2.4.6's
        # plugin-reload command without re-instantiating the plugin object.
        from .main_window import AssetsInspectorMainWindow

        if self._main_window is None:
            self._main_window = AssetsInspectorMainWindow(
                paths_bundle=paths,
                strings=get_strings(self._locale()),
                parent=self._parent_widget,
            )
        else:
            self._main_window.refresh(paths_bundle=paths)

        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    # --- helpers --------------------------------------------------------------

    def _locale(self) -> Locale:
        if self._organizer is None:
            return Locale.ZH_HANS
        raw = self._organizer.pluginSetting(self.NAME, "locale")
        try:
            return Locale(str(raw))
        except ValueError:
            return Locale.ZH_HANS


def create_plugin() -> BgsAssetsInspectorPlugin:
    return BgsAssetsInspectorPlugin()
