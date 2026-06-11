"""Per-model pricing table ownership for cost estimation."""

from __future__ import annotations

import tomllib
from datetime import date
from typing import Any

import tomli_w
from pydantic import BaseModel, Field

from bgs_translator.config import paths


class ModelPrice(BaseModel):
    """Provider model price in USD per one million tokens."""

    input_per_1m: float
    output_per_1m: float
    cache_read_per_1m: float | None = None


class Pricing(BaseModel):
    """Editable provider/model pricing table."""

    schema_version: int = 1
    updated_at: date | None = None
    providers: dict[str, dict[str, ModelPrice]] = Field(default_factory=dict)


def _default_providers() -> dict[str, dict[str, ModelPrice]]:
    return {
        "openai": {
            "gpt-5-mini": ModelPrice(input_per_1m=0.50, output_per_1m=2.00),
            "gpt-5": ModelPrice(input_per_1m=5.00, output_per_1m=20.00),
            "gpt-4o": ModelPrice(input_per_1m=2.50, output_per_1m=10.00),
            "gpt-4o-mini": ModelPrice(input_per_1m=0.15, output_per_1m=0.60),
        },
        "anthropic": {
            "claude-opus-4-7": ModelPrice(
                input_per_1m=15.00,
                output_per_1m=75.00,
                cache_read_per_1m=1.50,
            ),
            "claude-sonnet-4-7": ModelPrice(
                input_per_1m=3.00,
                output_per_1m=15.00,
                cache_read_per_1m=0.30,
            ),
        },
        "gemini": {
            "gemini-2.5-pro": ModelPrice(input_per_1m=1.25, output_per_1m=5.00),
            "gemini-2.5-flash": ModelPrice(input_per_1m=0.10, output_per_1m=0.40),
        },
        "deepseek": {
            "deepseek-chat": ModelPrice(input_per_1m=0.27, output_per_1m=1.10),
        },
    }


def default_pricing() -> Pricing:
    """Return the built-in PRD §4 pricing table."""
    return Pricing(providers=_default_providers())


def _read_pricing_dict() -> dict[str, Any]:
    pricing_file = paths.pricing_path()
    if not pricing_file.exists():
        return {}
    with pricing_file.open("rb") as handle:
        return tomllib.load(handle)


def _normalize_pricing_dict(raw: dict[str, Any]) -> dict[str, Any]:
    if "providers" in raw:
        return raw

    providers = {
        key: value
        for key, value in raw.items()
        if key not in {"schema_version", "updated_at"} and isinstance(value, dict)
    }
    return {
        "schema_version": raw.get("schema_version", 1),
        "updated_at": raw.get("updated_at"),
        "providers": providers,
    }


def _to_toml_dict(p: Pricing) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": p.schema_version}
    if p.updated_at is not None:
        payload["updated_at"] = p.updated_at
    for provider, models in p.providers.items():
        payload[provider] = {
            model: price.model_dump(mode="python", exclude_none=True)
            for model, price in models.items()
        }
    return payload


def load_pricing() -> Pricing:
    """Load pricing from disk, or return built-in defaults when missing."""
    raw = _read_pricing_dict()
    if not raw:
        return default_pricing()
    return Pricing.model_validate(_normalize_pricing_dict(raw))


def save_pricing(p: Pricing) -> None:
    """Persist pricing to TOML using the PRD's top-level provider table shape."""
    pricing_file = paths.pricing_path()
    pricing_file.parent.mkdir(parents=True, exist_ok=True)
    pricing_file.write_text(tomli_w.dumps(_to_toml_dict(p)), encoding="utf-8")


def get_price(p: Pricing, provider: str, model: str) -> ModelPrice | None:
    """Return a model price or None when missing."""
    return p.providers.get(provider, {}).get(model)


def estimate_cost(
    p: Pricing,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float | None:
    """Estimate USD cost for a provider/model/token tuple."""
    price = get_price(p, provider, model)
    if price is None:
        return None

    cache_price = price.cache_read_per_1m if price.cache_read_per_1m is not None else price.input_per_1m
    return (
        (input_tokens * price.input_per_1m)
        + (output_tokens * price.output_per_1m)
        + (cached_tokens * cache_price)
    ) / 1_000_000


__all__ = [
    "ModelPrice",
    "Pricing",
    "default_pricing",
    "estimate_cost",
    "get_price",
    "load_pricing",
    "save_pricing",
]
