"""Main inspector window - mod list with conflict summary.

Mirrors MO2's left-pane "Mods" view: one row per enabled mod, columns
match the user's reference screenshots (priority / name / conflicts /
files / source type). Double-click a row opens the per-mod detail dialog.

NOTE: No automated tests for this module — PyQt6 import fails in the
anaconda dev env (Qt DLL conflict), so offscreen Qt smoke tests cannot run
locally. Behavioral verification happens at Plan B Task 9 manual MO2
acceptance, where PyQt6 runs inside MO2's own embedded Python.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mo2_assets_engine.archive_order import (
    ArchiveLoadOrder,
    discover_archives_for_plugins,
)
from mo2_assets_engine.conflict_resolver import (
    ConflictResolver,
    resolve_all_winners,
)
from mo2_assets_engine.mod_enumerator import enumerate_mod_files
from mo2_assets_engine.profile import read_profile
from mo2_assets_engine.types import FileEntryKind

from .bridge import PathsBundle

if TYPE_CHECKING:
    from .localization import Strings


class AssetsInspectorMainWindow(QMainWindow):
    """Top-level inspector window. Holds the precomputed world state and
    exposes a refresh hook for the IPluginTool plugin to re-run on demand."""

    def __init__(
        self,
        *,
        paths_bundle: PathsBundle,
        strings: "Strings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._strings = strings
        self.setWindowTitle(strings.window_title)
        self.setMinimumSize(900, 520)

        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton(strings.refresh_button, central)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)
        outer.addLayout(toolbar)

        self.mod_table = QTableWidget(0, 5, central)
        self.mod_table.setHorizontalHeaderLabels(
            [
                strings.column_priority,
                strings.column_mod_name,
                strings.column_conflict_count,
                strings.column_file_count,
                strings.column_archive_type,
            ]
        )
        self.mod_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mod_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mod_table.verticalHeader().setVisible(False)
        self.mod_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        outer.addWidget(self.mod_table)

        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.mod_table.cellDoubleClicked.connect(self._on_row_double_clicked)

        self._paths_bundle = paths_bundle
        self.refresh(paths_bundle=paths_bundle)

    # --- public --------------------------------------------------------------

    def refresh(self, *, paths_bundle: PathsBundle) -> None:
        self._paths_bundle = paths_bundle
        self._world = _build_world(paths_bundle)
        self._populate_table()

    # --- handlers ------------------------------------------------------------

    def _on_refresh_clicked(self) -> None:
        self.refresh(paths_bundle=self._paths_bundle)

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        name_item = self.mod_table.item(row, 1)
        if name_item is None:
            return
        mod_name = name_item.text()
        # Lazy import to keep first-show latency low.
        from .mod_detail_dialog import ModDetailDialog

        dialog = ModDetailDialog(
            mod_name=mod_name,
            world=self._world,
            strings=self._strings,
            parent=self,
        )
        dialog.show()

    # --- rendering -----------------------------------------------------------

    def _populate_table(self) -> None:
        rows = self._world.summary_rows()
        self.mod_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self.mod_table.setItem(index, 0, _readonly_item(str(row["priority"])))
            self.mod_table.setItem(index, 1, _readonly_item(row["name"]))
            self.mod_table.setItem(index, 2, _readonly_item(str(row["conflicts"])))
            self.mod_table.setItem(index, 3, _readonly_item(str(row["files"])))
            self.mod_table.setItem(index, 4, _readonly_item(row["source_type"]))
        # Sort by priority descending (column 0).
        self.mod_table.sortItems(0, Qt.SortOrder.DescendingOrder)


def _readonly_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class _World:
    """Precomputed engine state for a given PathsBundle."""

    def __init__(self, paths_bundle: PathsBundle) -> None:
        profile = read_profile(
            profile_dir=paths_bundle.profile_dir,
            mods_root=paths_bundle.mods_root,
        )
        candidate_archives: list[str] = []
        for mod in profile.enabled_mods:
            if mod.root.exists():
                for child in mod.root.iterdir():
                    if child.is_file() and child.suffix.lower() in (".bsa", ".ba2"):
                        candidate_archives.append(child.name)
        archive_order: ArchiveLoadOrder = discover_archives_for_plugins(
            plugins=profile.enabled_plugins,
            candidate_archives=candidate_archives,
            game=paths_bundle.game,
        )
        self.profile = profile
        self.entries_by_mod = {
            mod.name: enumerate_mod_files(mod=mod, archive_order=archive_order)
            for mod in profile.enabled_mods
        }
        self.winners = resolve_all_winners(
            mods=profile.enabled_mods, entries_by_mod=self.entries_by_mod
        )
        self.resolver = ConflictResolver(
            mods=profile.enabled_mods, entries_by_mod=self.entries_by_mod
        )

    def summary_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for mod in self.profile.enabled_mods:
            entries = self.entries_by_mod.get(mod.name, [])
            conflicts = sum(
                1
                for e in entries
                if self.winners[e.relative_path].bucket.value != "no-conflict"
            )
            kinds = {e.kind for e in entries}
            if kinds == {FileEntryKind.LOOSE}:
                source_type = "loose"
            elif kinds == {FileEntryKind.ARCHIVED}:
                source_type = "archive"
            elif kinds == {FileEntryKind.LOOSE, FileEntryKind.ARCHIVED}:
                source_type = "mixed"
            else:
                source_type = "empty"
            rows.append(
                {
                    "priority": mod.priority,
                    "name": mod.name,
                    "conflicts": conflicts,
                    "files": len(entries),
                    "source_type": source_type,
                }
            )
        return rows


def _build_world(paths_bundle: PathsBundle) -> _World:
    return _World(paths_bundle)
