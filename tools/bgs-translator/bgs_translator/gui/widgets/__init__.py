"""Reusable Tk widget package for the control panel."""

from __future__ import annotations

from bgs_translator.gui.widgets.amber_checkbox import AmberCheckbox
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.amber_titlebar import AmberTitlebar, install_titlebar_styles
from bgs_translator.gui.widgets.empty_state import EmptyStatePanel
from bgs_translator.gui.widgets.progress_cell import ProgressCell, render_progress_bar
from bgs_translator.gui.widgets.scrollable_frame import ScrollableFrame
from bgs_translator.gui.widgets.secret_input import SecretInput
from bgs_translator.gui.widgets.status_bar import StatusBar

__all__ = [
    "AmberCheckbox",
    "AmberScrollbar",
    "AmberTitlebar",
    "EmptyStatePanel",
    "ProgressCell",
    "ScrollableFrame",
    "SecretInput",
    "StatusBar",
    "install_titlebar_styles",
    "render_progress_bar",
]
