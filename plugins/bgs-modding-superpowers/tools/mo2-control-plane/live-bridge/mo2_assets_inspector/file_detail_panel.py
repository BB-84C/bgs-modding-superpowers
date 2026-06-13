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

from mo2_assets_engine.rationale import rationale_for_bucket
from mo2_assets_engine.types import ConflictBucket, FileEntry, ResolvedWinner

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

    def show_winner(self, winner: ResolvedWinner) -> None:
        rationale = rationale_for_bucket(winner.bucket)
        winner_tag = _archive_tag(winner.winner)
        loser_lines = "\n".join(
            f"  - {loser.owner_mod} [{_archive_tag(loser)}]"
            for loser in winner.losers
        )
        body = (
            f"Path: {winner.relative_path}\n"
            f"Bucket: {winner.bucket.value}\n"
            f"\n"
            f"Winner: {winner.winner.owner_mod} [{winner_tag}]\n"
            f"Losers:\n{loser_lines or '  (none)'}\n"
            f"\n"
            f"{self._strings.rationale_header}:\n{rationale.short}\n"
            f"\n"
            f"{self._strings.kb_reference_header}:\n"
            + "\n".join(f"  - {rid}" for rid in rationale.kb_record_ids)
        )
        self._browser.setPlainText(body)

    def show_no_conflict_path(self, path: str) -> None:
        rationale = rationale_for_bucket(ConflictBucket.NO_CONFLICT)
        body = (
            f"Path: {path}\n"
            f"Bucket: {ConflictBucket.NO_CONFLICT.value}\n"
            f"\n"
            f"{self._strings.rationale_header}:\n{rationale.short}\n"
            f"\n"
            f"{self._strings.kb_reference_header}:\n"
            + "\n".join(f"  - {rid}" for rid in rationale.kb_record_ids)
        )
        self._browser.setPlainText(body)


def _archive_tag(entry: FileEntry) -> str:
    if entry.archive is None:
        return "loose"
    return f"{entry.archive.kind.value}:{entry.archive.name}"
