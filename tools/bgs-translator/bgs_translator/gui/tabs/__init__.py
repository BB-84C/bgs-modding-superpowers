"""Tk notebook tab package for the control panel."""

from __future__ import annotations

from bgs_translator.gui.tabs.batches_tab import BatchesTab
from bgs_translator.gui.tabs.entries_tab import EntriesTab
from bgs_translator.gui.tabs.glossary_tab import GlossaryTab
from bgs_translator.gui.tabs.logs_tab import LogsTab
from bgs_translator.gui.tabs.profiles_tab import ProfilesTab
from bgs_translator.gui.tabs.project_tab import ProjectTab
from bgs_translator.gui.tabs.prompt_tab import PromptTab

__all__ = [
    "BatchesTab",
    "EntriesTab",
    "GlossaryTab",
    "LogsTab",
    "ProfilesTab",
    "ProjectTab",
    "PromptTab",
]
