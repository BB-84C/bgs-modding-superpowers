"""Token and provider-cost accounting ownership."""

from __future__ import annotations

from bgs_translator.config.pricing import Pricing, estimate_cost, load_pricing
from bgs_translator.config.profiles import ProviderProfile
from bgs_translator.pipeline.clients.base import TokenUsage


class CostTracker:
    """Tracks provider spend across batches with cap enforcement."""

    def __init__(
        self,
        profile: ProviderProfile,
        project_cap: float | None = None,
        pricing: Pricing | None = None,
    ) -> None:
        self.profile = profile
        self.project_cap = project_cap
        self.pricing = pricing or load_pricing()
        self._total = 0.0
        self.cost_exact = True

    def record(self, usage: TokenUsage, exact_cost: float | None) -> None:
        """Record exact provider cost or estimate from local pricing."""

        if exact_cost is not None:
            cost = exact_cost
            exact = True
        else:
            estimated = estimate_cost(
                self.pricing,
                self.profile.sdk_kind,
                self.profile.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.cached_tokens,
            )
            cost = estimated if estimated is not None else 0.0
            exact = False
        self._total += cost
        self.cost_exact = self.cost_exact and exact

    def estimated_total(self) -> float:
        """Return cumulative cost in USD-equivalent units."""

        return self._total

    def would_exceed_cap(self, additional_estimated: float) -> bool:
        """Return true if adding the estimate would exceed profile or project cap."""

        next_total = self._total + additional_estimated
        caps = [cap for cap in (self.profile.cost_cap_usd, self.project_cap) if cap is not None]
        return any(next_total > cap for cap in caps)


__all__ = ["CostTracker"]
