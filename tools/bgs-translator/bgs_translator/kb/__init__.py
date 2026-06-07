"""Read-only bgs-kb integration package."""

from bgs_translator.kb.glossary import GlossaryComposer, GlossarySubset
from bgs_translator.kb.models import GlossaryEntry, ResolvedTerm
from bgs_translator.kb.reader import KBGlossaryReader

__all__ = ["GlossaryComposer", "GlossaryEntry", "GlossarySubset", "KBGlossaryReader", "ResolvedTerm"]
