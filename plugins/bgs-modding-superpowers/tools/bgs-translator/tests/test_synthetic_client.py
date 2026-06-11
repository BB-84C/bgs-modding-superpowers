"""Tests for the synthetic LLM client."""

from __future__ import annotations

from bgs_translator.parsers.tes4_family import TranslationUnit


async def test_synthetic_translate_batch_returns_items_keyed_correctly() -> None:
    from bgs_translator.pipeline.batcher import Batch
    from bgs_translator.pipeline.clients.synthetic import SyntheticLLMClient
    from bgs_translator.pipeline.mask import build_masked_unit

    items = [
        build_masked_unit(TranslationUnit("Test.esp", 1, 1, "EDID", "WEAP", "FULL", source="Hello")),
        build_masked_unit(TranslationUnit("Test.esp", 2, 2, "EDID2", "WEAP", "FULL", source="World")),
    ]
    batch = Batch("batch-1", items, None, [], [])
    response = await SyntheticLLMClient().translate_batch(batch, "system prompt")
    assert response.items == {"I1": "Hello", "I2": "World"}
    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0
    assert response.via == "synthetic"
