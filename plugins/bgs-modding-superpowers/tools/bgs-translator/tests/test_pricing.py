"""Tests for pricing persistence and estimation."""

from __future__ import annotations


def test_load_defaults_when_missing(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.pricing import load_pricing

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    pricing = load_pricing()

    assert pricing.providers["openai"]["gpt-5-mini"].input_per_1m == 0.50
    assert pricing.providers["anthropic"]["claude-opus-4-7"].cache_read_per_1m == 1.50
    assert pricing.providers["deepseek"]["deepseek-chat"].output_per_1m == 1.10


def test_get_price_known_model(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.pricing import get_price, load_pricing

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    assert get_price(load_pricing(), "openai", "gpt-5-mini") is not None


def test_get_price_unknown_returns_none(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.pricing import get_price, load_pricing

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    assert get_price(load_pricing(), "vault-tec", "zax-1.3c") is None


def test_estimate_cost_basic(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.pricing import estimate_cost, load_pricing

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    cost = estimate_cost(load_pricing(), "openai", "gpt-5-mini", 1000, 500)

    assert cost == 0.0015


def test_estimate_cost_with_cache_read(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.pricing import estimate_cost, load_pricing

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    cost = estimate_cost(load_pricing(), "anthropic", "claude-sonnet-4-7", 1000, 1000, 1000)

    assert cost == 0.0183
