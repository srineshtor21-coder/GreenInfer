"""
GreenInfer Orchestrator
The central class that ties all components together.

This is the main entry point for developers using the framework.
It coordinates prompt optimization, complexity scoring, energy estimation,
carbon-aware routing, and cascade inference into a single clean interface.
"""

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from .complexity_scorer import score_prompt, ComplexityResult
from .energy_estimator import EnergyEstimator, InferenceMetrics
from .model_registry import ModelRegistry, DEFAULT_MODEL_POOL
from .cascade import CascadeEngine
from .carbon_router import CarbonRouter

logger = logging.getLogger("greeninfer")


@dataclass
class GreenInferResult:
    """
    Complete result from a GreenInfer inference call.
    Contains the response plus full transparency metrics.
    """
    # The actual response
    response: str

    # Routing decisions
    model_tier: str
    model_id: str
    mode_used: str
    escalations: int
    cascade_path: list[str]

    # Prompt optimization
    original_prompt: str
    optimized_prompt: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    reduction_pct: int
    optimizer_used: bool

    # Complexity analysis
    complexity_score: float
    complexity_score_100: int
    complexity_label: str
    accuracy_req: str
    complexity_features: dict

    # Energy and carbon
    energy_mwh: float
    energy_joules: float
    co2_grams: float
    grid_intensity: float
    baseline_energy_mwh: float
    energy_saved_mwh: float
    energy_saved_pct: int
    measurement_method: str

    # Grid info
    grid_status: str = "Unknown"
    carbon_mode_override: bool = False

    # Timing
    latency_ms: int = 0

    # Session cumulative totals
    session_energy_mwh: float = 0.0
    session_co2_grams: float = 0.0
    session_prompt_count: int = 0


class GreenInfer:
    """
    Green Orchestration Framework for energy-efficient LLM inference.

    Routes every prompt to the minimum-energy model capable of answering
    accurately. Combines prompt optimization, complexity scoring, cascade
    inference, and real-time carbon-aware routing.

    Completely model-agnostic - works with any provider: Groq, OpenAI,
    Anthropic, Hugging Face, or local models.

    Basic usage:
        from greeninfer import GreenInfer

        gi = GreenInfer()
        result = gi.chat("What is the capital of France?")
        print(result.response)
        print(f"Energy: {result.energy_mwh} mWh | CO2: {result.co2_grams}g")

    Custom model pool:
        gi = GreenInfer(
            model_pool={
                "small":  {"provider": "groq", "model": "llama-3.2-1b-preview",
                           "api_key_env": "GROQ_API_KEY", "energy_mwh": 0.9},
                "medium": {"provider": "openai", "model": "gpt-4o-mini",
                           "api_key_env": "OPENAI_API_KEY", "energy_mwh": 8.0},
                "large":  {"provider": "openai", "model": "gpt-4o",
                           "api_key_env": "OPENAI_API_KEY", "energy_mwh": 95.0},
            }
        )

    With carbon-aware routing:
        gi = GreenInfer(
            carbon_aware=True,
            electricity_maps_key="your_key_here"
        )
    """

    def __init__(
        self,
        model_pool: dict = None,
        optimizer_model: str = None,
        mode: str = "balanced",
        carbon_aware: bool = False,
        carbon_budget_g: float = None,
        electricity_maps_key: str = None,
        groq_api_key: str = None,
    ):
        """
        Args:
            model_pool:           Dict of tier configs. Uses Groq Llama3 pool by default.
            optimizer_model:      HF model name for your prompt optimizer.
                                  Defaults to "sirenice/GreenPromptsOptimizer".
            mode:                 Default routing mode: "eco"/"balanced"/"performance".
            carbon_aware:         If True, fetches real-time grid data to adjust routing.
            carbon_budget_g:      Per-session CO2 budget in grams (e.g. 5.0).
            electricity_maps_key: API key for ElectricityMaps (optional, uses ERCOT estimates if absent).
            groq_api_key:         Groq API key. Falls back to GROQ_API_KEY env var.
        """
        self.default_mode = mode
        self.carbon_budget_g = carbon_budget_g
        self._carbon_used_g = 0.0

        # Initialize model registry
        if model_pool:
            from .model_registry import ModelConfig
            pool = {}
            for tier, cfg in model_pool.items():
                pool[tier] = ModelConfig(
                    tier=tier,
                    provider=cfg.get("provider", "groq"),
                    model_id=cfg.get("model", ""),
                    api_key_env=cfg.get("api_key_env", "GROQ_API_KEY"),
                    energy_mwh=cfg.get("energy_mwh", 10.0),
                    params_b=cfg.get("params_b", 0.0),
                )
            self.registry = ModelRegistry(pool)
        else:
            self.registry = ModelRegistry()

        # Initialize prompt optimizer
        self._optimizer = None
        hf_model = optimizer_model or os.environ.get(
            "HF_MODEL_NAME", "sirenice/GreenPromptsOptimizer"
        )
        self._load_optimizer(hf_model)

        # Initialize Groq client
        key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
        groq_client = None
        if key:
            try:
                from groq import Groq
                groq_client = Groq(api_key=key)
                logger.info("Groq client initialized")
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

        # Initialize cascade engine
        self.cascade = CascadeEngine(groq_client=groq_client)

        # Initialize energy estimator
        self.energy = EnergyEstimator()

        # Initialize carbon router
        self.carbon_router = None
        if carbon_aware:
            self.carbon_router = CarbonRouter(
                electricity_maps_key=electricity_maps_key
                or os.environ.get("ELECTRICITY_MAPS_KEY")
            )
            logger.info("Carbon-aware routing enabled")

    def _load_optimizer(self, model_name: str):
        """Load prompt optimizer from Hugging Face."""
        if not model_name:
            return
        try:
            from transformers import pipeline
            logger.info(f"Loading prompt optimizer: {model_name}")
            self._optimizer = pipeline(
                "text2text-generation",
                model=model_name,
                max_new_tokens=128,
            )
            logger.info("Prompt optimizer loaded")
        except Exception as e:
            logger.warning(f"Could not load optimizer ({e}). Proceeding without it.")

    def _optimize_prompt(self, text: str) -> tuple[str, bool]:
        """Run prompt through optimizer. Returns (optimized, was_used)."""
        if self._optimizer is None:
            return text, False
        try:
            result = self._optimizer(text, max_new_tokens=128)
            optimized = result[0]["generated_text"].strip()
            if len(optimized) < 5 or len(optimized.split()) < 2:
                return text, False
            return optimized, True
        except Exception as e:
            logger.warning(f"Optimizer failed: {e}")
            return text, False

    def _resolve_mode(self, mode: str) -> str:
        """
        Determine final routing mode.
        Carbon router can override user-selected mode if grid is dirty.
        """
        if self.carbon_router:
            grid = self.carbon_router.get_grid_status()
            self.energy.update_grid_intensity(grid.intensity)
            # Only override if grid is dirtier than current mode allows
            if grid.recommended_mode == "eco" and mode != "eco":
                logger.info(f"Carbon router overriding mode to eco (grid: {grid.intensity} gCO2/kWh)")
                return "eco"
        return mode

    def chat(self, prompt: str, mode: str = None) -> GreenInferResult:
        """
        Main inference method. Runs the full Green Orchestration Pipeline.

        Args:
            prompt: The user's input prompt
            mode:   Override routing mode for this call ("eco"/"balanced"/"performance")

        Returns:
            GreenInferResult with response and full energy/carbon metrics
        """
        wall_start = time.time()
        used_mode = mode or self.default_mode

        # Step 1: Grid-aware mode resolution
        grid_status = "No data"
        carbon_override = False
        if self.carbon_router:
            grid = self.carbon_router.get_grid_status()
            grid_status = f"{grid.label} ({grid.intensity:.0f} gCO2/kWh)"
            resolved_mode = self._resolve_mode(used_mode)
            carbon_override = (resolved_mode != used_mode)
            used_mode = resolved_mode
        
        # Step 2: Prompt optimization
        original_tokens = len(prompt.split())
        optimized, optimizer_used = self._optimize_prompt(prompt)
        optimized_tokens = len(optimized.split())
        tokens_saved = max(0, original_tokens - optimized_tokens)
        reduction_pct = round((tokens_saved / original_tokens) * 100) if original_tokens > 0 else 0

        # Step 3: Complexity scoring
        complexity: ComplexityResult = score_prompt(prompt, used_mode)
        logger.info(
            f"Complexity: {complexity.score_100}/100 ({complexity.label}) "
            f"-> {complexity.tier} | mode={used_mode}"
        )

        # Step 4: Check carbon budget
        budget_remaining = None
        if self.carbon_budget_g is not None:
            budget_remaining = self.carbon_budget_g - self._carbon_used_g

        # Step 5: Cascade inference
        cascade_result = self.cascade.run(
            prompt=optimized,
            start_tier=complexity.tier,
            registry=self.registry,
            min_complexity=complexity.score,
            carbon_budget_remaining=budget_remaining,
        )

        # Step 6: Record energy metrics
        metrics: InferenceMetrics = self.energy.record(
            model_tier=cascade_result.final_tier,
            model_id=cascade_result.model_id,
            input_tokens=optimized_tokens,
            output_tokens=cascade_result.output_tokens,
            latency_ms=cascade_result.latency_ms,
        )

        # Update carbon budget
        self._carbon_used_g += metrics.co2_grams

        total_latency = round((time.time() - wall_start) * 1000)

        return GreenInferResult(
            response=cascade_result.response,
            model_tier=cascade_result.final_tier,
            model_id=cascade_result.model_id,
            mode_used=used_mode,
            escalations=cascade_result.escalations,
            cascade_path=cascade_result.cascade_path,
            original_prompt=prompt,
            optimized_prompt=optimized,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            tokens_saved=tokens_saved,
            reduction_pct=reduction_pct,
            optimizer_used=optimizer_used,
            complexity_score=complexity.score,
            complexity_score_100=complexity.score_100,
            complexity_label=complexity.label,
            accuracy_req=complexity.accuracy_req,
            complexity_features=complexity.features,
            energy_mwh=metrics.energy_mwh,
            energy_joules=metrics.energy_joules,
            co2_grams=metrics.co2_grams,
            grid_intensity=metrics.grid_intensity,
            baseline_energy_mwh=metrics.baseline_energy_mwh,
            energy_saved_mwh=metrics.energy_saved_mwh,
            energy_saved_pct=metrics.energy_saved_pct,
            measurement_method=metrics.measurement_method,
            grid_status=grid_status,
            carbon_mode_override=carbon_override,
            latency_ms=total_latency,
            session_energy_mwh=metrics.session_energy_mwh,
            session_co2_grams=metrics.session_co2_grams,
            session_prompt_count=metrics.session_prompt_count,
        )

    def session_summary(self) -> dict:
        """Return cumulative session energy and carbon metrics."""
        summary = self.energy.session_summary()
        if self.carbon_budget_g:
            summary["carbon_budget_g"] = self.carbon_budget_g
            summary["carbon_used_g"]   = round(self._carbon_used_g, 6)
            summary["carbon_remaining_g"] = round(
                max(0, self.carbon_budget_g - self._carbon_used_g), 6
            )
        return summary

    def reset_session(self):
        """Reset session counters and carbon budget."""
        self.energy.reset_session()
        self._carbon_used_g = 0.0
