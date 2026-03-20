"""
GreenInfer - Green Orchestration Framework for energy-efficient LLM inference.

A model-agnostic framework that routes prompts to the most energy-efficient
model capable of answering accurately, combining prompt optimization,
complexity scoring, cascade inference, and carbon-aware routing.

Usage:
    from greeninfer import GreenInfer

    gi = GreenInfer(
        model_pool={
            "small":  {"provider": "groq", "model": "llama-3.2-1b-preview"},
            "medium": {"provider": "groq", "model": "llama-3.1-8b-instant"},
            "large":  {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        },
        optimizer_model="sirenice/GreenPromptsOptimizer",
        mode="balanced"
    )

    result = gi.chat("Explain quantum entanglement")
    print(result.response)
    print(result.energy_mwh, "mWh used")
    print(result.co2_grams, "g CO2 emitted")
"""

from .orchestrator import GreenInfer
from .complexity_scorer import score_prompt, ComplexityResult
from .energy_estimator import EnergyEstimator, InferenceMetrics
from .cascade import CascadeEngine
from .model_registry import ModelRegistry
from .carbon_router import CarbonRouter

__version__ = "0.1.0"
__author__  = "Srinesh Toranala"
__license__ = "MIT"

__all__ = [
    "GreenInfer",
    "score_prompt",
    "ComplexityResult",
    "EnergyEstimator",
    "InferenceMetrics",
    "CascadeEngine",
    "ModelRegistry",
    "CarbonRouter",
]
