"""Read-only bgs-kb integration package."""

from bgs_translator.kb.glossary import GlossaryComposer, GlossarySubset
from bgs_translator.kb.models import GlossaryEntry, GlossaryMatchEvidence, ResolvedTerm
from bgs_translator.kb.reader import KBGlossaryReader
from bgs_translator.kb.retriever import GlossaryRetrievalResult, GlossaryRetriever

__all__ = [
    "GlossaryComposer",
    "GlossaryEntry",
    "GlossaryMatchEvidence",
    "GlossaryRetrievalResult",
    "GlossaryRetriever",
    "GlossarySubset",
    "KBGlossaryReader",
    "ResolvedTerm",
]
