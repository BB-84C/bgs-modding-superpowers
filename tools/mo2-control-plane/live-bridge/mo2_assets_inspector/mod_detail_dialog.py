"""Per-mod conflict detail dialog.

Mirrors MO2's `信息 → 冲突 → 常规` tab from the user's reference screenshots,
extended with archive-bucket entries (loose + BA2/BSA in one view).
Layout: three sections on the left, a file-detail panel on the right
showing per-entry rationale + KB citation.

NOTE: No automated tests for this module - PyQt6 import fails in the
anaconda dev env. Behavioral verification at Plan B Task 9 manual MO2
acceptance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mo2_assets_engine.types import ConflictBucket, FileEntry, ResolvedWinner

if TYPE_CHECKING:
    from .localization import Strings
    from .main_window import _World


class ModDetailDialog(QDialog):
    def __init__(
        self,
        *,
        mod_name: str,
        world: "_World",
        strings: "Strings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mod_name = mod_name
        self._world = world
        self._strings = strings
        self.setWindowTitle(f"Conflicts — {mod_name}")
        self.resize(1100, 640)

        report = world.resolver.report_for_mod(mod_name)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        sections_widget = QWidget(splitter)
        sections_layout = QVBoxLayout(sections_widget)

        self.kept_tree = _build_winner_tree(
            title=f"{strings.section_kept} ({len(report.kept)})",
            entries=report.kept,
            kind_column_header=strings.column_overridden_by,
            strings=strings,
        )
        self.overwritten_tree = _build_winner_tree(
            title=f"{strings.section_overwritten} ({len(report.overwritten)})",
            entries=report.overwritten,
            kind_column_header=strings.column_overrider,
            strings=strings,
        )
        self.no_conflict_tree = _build_no_conflict_tree(
            title=f"{strings.section_no_conflict} ({len(report.no_conflict)})",
            entries=report.no_conflict,
            file_column_header=strings.column_file,
        )

        sections_layout.addWidget(self.kept_tree)
        sections_layout.addWidget(self.overwritten_tree)
        sections_layout.addWidget(self.no_conflict_tree)
        splitter.addWidget(sections_widget)

        # File detail panel (Task 8); lazy import.
        from .file_detail_panel import FileDetailPanel

        self.detail_panel = FileDetailPanel(strings=strings, parent=splitter)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer = QHBoxLayout(self)
        outer.addWidget(splitter)

        # Wire selection -> detail panel.
        for tree, picker in (
            (self.kept_tree, self._pick_kept),
            (self.overwritten_tree, self._pick_overwritten),
            (self.no_conflict_tree, self._pick_no_conflict),
        ):
            tree.itemSelectionChanged.connect(picker)

    # --- selection routing ----------------------------------------------------

    def _pick_kept(self) -> None:
        winner = _selected_winner(self.kept_tree)
        if winner is not None:
            self.detail_panel.show_winner(winner)

    def _pick_overwritten(self) -> None:
        winner = _selected_winner(self.overwritten_tree)
        if winner is not None:
            self.detail_panel.show_winner(winner)

    def _pick_no_conflict(self) -> None:
        item = self.no_conflict_tree.currentItem()
        if item is None:
            return
        self.detail_panel.show_no_conflict_path(item.text(0))


def _build_winner_tree(
    *,
    title: str,
    entries: list[ResolvedWinner],
    kind_column_header: str,
    strings: "Strings",
) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels([strings.column_file, kind_column_header])
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    tree.setObjectName(title)
    for entry in entries:
        row = QTreeWidgetItem(
            [
                entry.relative_path,
                _format_other_party(entry),
            ]
        )
        row.setData(0, Qt.ItemDataRole.UserRole, entry)
        tree.addTopLevelItem(row)
    return tree


def _build_no_conflict_tree(
    *,
    title: str,
    entries: list[FileEntry],
    file_column_header: str,
) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderLabels([file_column_header])
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    tree.setObjectName(title)
    for entry in entries:
        row = QTreeWidgetItem([entry.relative_path])
        tree.addTopLevelItem(row)
    return tree


def _selected_winner(tree: QTreeWidget) -> ResolvedWinner | None:
    item = tree.currentItem()
    if item is None:
        return None
    data = item.data(0, Qt.ItemDataRole.UserRole)
    if isinstance(data, ResolvedWinner):
        return data
    return None


def _format_other_party(entry: ResolvedWinner) -> str:
    # Kept-tree -> show all losers; Overwritten-tree -> show the single winner.
    bucket = entry.bucket
    is_overwritten_perspective = bucket in {
        ConflictBucket.LOOSE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.ARCHIVE_OVERWRITTEN_BY_LOOSE,
        ConflictBucket.ARCHIVE_OVERWRITTEN_BY_ARCHIVE,
    }
    if is_overwritten_perspective:
        return f"{entry.winner.owner_mod} [{_archive_tag(entry.winner)}]"
    # Kept perspective: list all losers.
    tags = ", ".join(
        f"{loser.owner_mod} [{_archive_tag(loser)}]" for loser in entry.losers
    )
    return tags


def _archive_tag(entry: FileEntry) -> str:
    if entry.archive is None:
        return "loose"
    return f"{entry.archive.kind.value}:{entry.archive.name}"
