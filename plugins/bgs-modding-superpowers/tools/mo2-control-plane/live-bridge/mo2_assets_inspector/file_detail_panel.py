"""Right-hand file detail panel.

Renders the full resolution rationale + KB citation for one selected entry.
The body is a plain QTextBrowser (read-only). KB record IDs are displayed
as plain text the user can paste into `bgs_kb_get`.

NOTE: No automated tests for this module - PyQt6 import fails in the
anaconda dev env. Behavioral verification at Plan B Task 9 manual MO2
acceptance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from mo2_assets_engine.conflict_resolver import ResolvedFile
from mo2_assets_engine.virtual_data_tree import SourceType

if TYPE_CHECKING:
    from .localization import Strings


class FileDetailPanel(QWidget):
    def __init__(self, *, strings: "Strings", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._strings = strings
        layout = QVBoxLayout(self)
        self._browser = QTextBrowser(self)
        self._browser.setOpenExternalLinks(False)
        layout.addWidget(self._browser)

    def body_text(self) -> str:
        return self._browser.toPlainText()

    def show_winner(self, winner: ResolvedFile) -> None:
        winner_tag = _archive_tag(winner.winner)
        loser_lines = "\n".join(
            f"  - {loser.source_mod} [{_archive_tag(loser)}]"
            for loser in winner.losers
        )
        body = (
            f"Path: {winner.relative_path}\n"
            f"Conflict: {winner.is_conflict}\n"
            f"\n"
            f"Winner: {winner.winner.source_mod} [{winner_tag}]\n"
            f"Losers:\n{loser_lines or '  (none)'}\n"
            f"\n"
            f"{self._strings.rationale_header}:\n{_rationale_for(winner)}"
        )
        self._browser.setPlainText(body)

    def show_no_conflict_path(self, path: str) -> None:
        body = (
            f"Path: {path}\n"
            f"Conflict: False\n"
            f"\n"
            f"{self._strings.rationale_header}:\nNo other provider contributes this virtual Data path."
        )
        self._browser.setPlainText(body)


def _archive_tag(entry) -> str:
    if entry.archive_name is None:
        return "loose"
    return f"archive:{entry.archive_name}"


def _rationale_for(resolved: ResolvedFile) -> str:
    if resolved.winner.source_type is SourceType.LOOSE:
        if any(loser.source_type is SourceType.ARCHIVE for loser in resolved.losers):
            return "Loose files override archived assets at the same virtual Data path."
        return "Among loose-file providers, the highest MO2 mod priority wins."
    return "Among archive providers, the archive attached to the later plugin load order wins."
