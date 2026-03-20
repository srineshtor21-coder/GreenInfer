"""
GreenInfer Model Registry
Manages the pool of available models and their energy profiles.
Designed to be completely model-agnostic - add any model without
touching orchestration code.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("greeninfer.registry")


@dataclass
class ModelConfig:
    """
    Configuration for a single model in the pool.
    
    Attributes:
        tier:           "small" / "medium" / "large"
        provider:       "groq" / "openai" / "huggingface" / "local" / "anthropic"
        model_id:       Model name/ID as expected by the provider
        api_key_env:    Name of the environment variable holding the API key
        energy_mwh:     Estimated energy per inference in milliwatt-hours
        co2_g_per_mwh:  CO2 grams per mWh (grid-dependent, default ERCOT avg)
        max_tokens:     Max output tokens
        context_window: Max input tokens this model supports
        params_b:       Model parameter count in billions (for display)
        description:    Human-readable description
    """
    tier: str
    provider: str
    model_id: str
    api_key_env: str
    energy_mwh: float
    co2_g_per_mwh: float = 0.198    # ERCOT Texas grid average gCO2/kWh / 1000
    max_tokens: int = 600
    context_window: int = 8192
    params_b: float = 0.0
    description: str = ""


# Default model pool using Groq (free, fast, high quality)
# Developers can override this entirely with their own models
DEFAULT_MODEL_POOL = {
    "small": ModelConfig(
        tier="small",
        provider="groq",
        model_id="llama-3.2-1b-preview",
        api_key_env="GROQ_API_KEY",
        energy_mwh=0.9,
        params_b=1.0,
        description="Fast 1B model for simple factual queries"
    ),
    "medium": ModelConfig(
        tier="medium",
        provider="groq",
        model_id="llama-3.1-8b-instant",
        api_key_env="GROQ_API_KEY",
        energy_mwh=3.8,
        params_b=8.0,
        description="Capable 8B model for moderate reasoning tasks"
    ),
    "large": ModelConfig(
        tier="large",
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        energy_mwh=48.0,
        params_b=70.0,
        description="Full 70B model for complex reasoning and analysis"
    ),
}


class ModelRegistry:
    """
    Manages available models and provides energy-aware selection.
    
    Completely model-agnostic - supports any provider that follows
    the standard chat completion interface.
    
    Example:
        registry = ModelRegistry()
        # Add a custom OpenAI model
        registry.register("xlarge", ModelConfig(
            tier="xlarge",
            provider="openai",
            model_id="gpt-4o",
            api_key_env="OPENAI_API_KEY",
            energy_mwh=120.0,
            params_b=200.0
        ))
    """

    def __init__(self, model_pool: dict = None):
        self._pool: dict[str, ModelConfig] = {}
        pool = model_pool or DEFAULT_MODEL_POOL
        for tier, config in pool.items():
            self.register(tier, config)

    def register(self, tier: str, config: ModelConfig):
        """Add or replace a model tier in the registry."""
        self._pool[tier] = config
        logger.info(f"Registered {tier} model: {config.model_id} ({config.provider})")

    def get(self, tier: str) -> Optional[ModelConfig]:
        """Get config for a specific tier."""
        return self._pool.get(tier)

    def tiers(self) -> list[str]:
        """Return all registered tiers in order from smallest to largest."""
        order = {"small": 0, "medium": 1, "large": 2, "xlarge": 3}
        return sorted(self._pool.keys(), key=lambda t: order.get(t, 99))

    def tiers_from(self, start_tier: str) -> list[str]:
        """Return all tiers from start_tier upward (for cascade)."""
        all_tiers = self.tiers()
        if start_tier not in all_tiers:
            return all_tiers
        idx = all_tiers.index(start_tier)
        return all_tiers[idx:]

    def energy_for_tier(self, tier: str) -> float:
        config = self._pool.get(tier)
        return config.energy_mwh if config else 0.0

    def baseline_energy(self) -> float:
        """Energy if we always used the largest model (the wasteful baseline)."""
        largest = self.tiers()[-1]
        return self.energy_for_tier(largest)

    def summary(self) -> list[dict]:
        """Return a summary of all registered models for display/logging."""
        return [
            {
                "tier": t,
                "model": c.model_id,
                "provider": c.provider,
                "energy_mwh": c.energy_mwh,
                "params_b": c.params_b,
            }
            for t, c in self._pool.items()
        ]
