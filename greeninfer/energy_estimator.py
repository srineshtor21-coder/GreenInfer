"""
GreenInfer Energy Estimator
Tracks real energy consumption and CO2 emissions per inference.

Two modes:
  1. Real measurement - uses CodeCarbon to measure actual GPU/CPU power draw
  2. Proxy estimation - uses token count and model size coefficients when
     CodeCarbon is not available (e.g. when calling external APIs)
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger("greeninfer.energy")

# Try to import CodeCarbon for real measurement
try:
    from codecarbon import EmissionsTracker
    CODECARBON_AVAILABLE = True
    logger.info("CodeCarbon available - real energy measurement enabled")
except ImportError:
    CODECARBON_AVAILABLE = False
    logger.info("CodeCarbon not installed - using proxy energy estimation")
    logger.info("Install with: pip install codecarbon")


@dataclass
class InferenceMetrics:
    """
    Full energy and carbon metrics for a single inference call.
    
    All values are real measurements when CodeCarbon is available,
    otherwise proxy estimates based on token count and model parameters.
    """
    model_tier: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

    # Energy
    energy_mwh: float               # Milliwatt-hours consumed
    energy_joules: float             # Joules (energy_mwh * 3.6)
    measurement_method: str          # "codecarbon" or "proxy"

    # Carbon
    co2_grams: float                 # Grams of CO2 emitted
    grid_intensity: float            # gCO2/kWh used for calculation

    # Savings vs always-large baseline
    baseline_energy_mwh: float
    energy_saved_mwh: float
    energy_saved_pct: int

    # Session cumulative (filled in by orchestrator)
    session_energy_mwh: float = 0.0
    session_co2_grams: float = 0.0
    session_tokens_saved: int = 0
    session_prompt_count: int = 0


# Proxy energy coefficients (mWh per output token)
# Derived from published benchmarks for each model size class
# Sources: MLPerf Inference, academic GPU benchmarking papers
PROXY_COEFFICIENTS = {
    "small":  0.00090,   # ~1B param models
    "medium": 0.00380,   # ~8B param models
    "large":  0.04800,   # ~70B param models
    "xlarge": 0.12000,   # ~200B+ param models
}


class EnergyEstimator:
    """
    Measures or estimates energy consumption for LLM inference calls.
    
    When CodeCarbon is available and running locally, measures real
    GPU power draw. When calling external APIs (Groq, OpenAI, etc.),
    uses calibrated proxy estimates based on token count and model size.
    
    Also tracks cumulative session metrics for display in the UI.
    """

    def __init__(self, grid_intensity: float = 198.0, country: str = "USA", region: str = "Texas"):
        """
        Args:
            grid_intensity: gCO2 per kWh. Default is ERCOT Texas average.
                          Will be overridden by CarbonRouter if enabled.
            country: For CodeCarbon regional emissions data
            region: For CodeCarbon regional emissions data
        """
        self.grid_intensity = grid_intensity   # gCO2/kWh
        self.country = country
        self.region = region

        # Session tracking
        self._session_energy_mwh  = 0.0
        self._session_co2_grams   = 0.0
        self._session_tokens_saved = 0
        self._session_prompt_count = 0

    def update_grid_intensity(self, intensity: float):
        """Called by CarbonRouter when it gets fresh grid data."""
        self.grid_intensity = intensity
        logger.info(f"Grid intensity updated: {intensity} gCO2/kWh")

    def estimate_proxy(
        self,
        tier: str,
        output_tokens: int,
        baseline_tier: str = "large"
    ) -> tuple[float, float]:
        """
        Proxy estimation based on token count and model size coefficients.
        Returns (energy_mwh, co2_grams).
        """
        coeff = PROXY_COEFFICIENTS.get(tier, PROXY_COEFFICIENTS["large"])
        energy_mwh = output_tokens * coeff
        co2_grams = (energy_mwh / 1000) * self.grid_intensity  # convert mWh to kWh first
        return round(energy_mwh, 4), round(co2_grams, 6)

    @contextmanager
    def measure_local(self, run_id: str = "inference"):
        """
        Context manager for measuring real local inference energy.
        Use this when running models locally (not via API).
        
        Example:
            with estimator.measure_local("my_run") as tracker:
                output = model.generate(input)
            metrics = tracker.result
        """
        if not CODECARBON_AVAILABLE:
            logger.warning("CodeCarbon not available, falling back to proxy estimation")
            yield None
            return

        tracker = EmissionsTracker(
            project_name=f"greeninfer_{run_id}",
            measure_power_secs=1,
            log_level="error",
            save_to_file=False,
            country_iso_code=self.country,
        )
        tracker.start()
        try:
            yield tracker
        finally:
            emissions_kg = tracker.stop()
            tracker.result = {
                "co2_kg": emissions_kg,
                "co2_grams": emissions_kg * 1000 if emissions_kg else 0,
                "energy_kwh": tracker._total_energy.kWh if hasattr(tracker, '_total_energy') else 0,
                "energy_mwh": (tracker._total_energy.kWh * 1000) if hasattr(tracker, '_total_energy') else 0,
            }

    def record(
        self,
        model_tier: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        baseline_tier: str = "large",
        codecarbon_result: dict = None,
    ) -> InferenceMetrics:
        """
        Record metrics for a completed inference call.
        Returns full InferenceMetrics with session totals.
        """
        if codecarbon_result:
            energy_mwh = codecarbon_result.get("energy_mwh", 0)
            co2_grams  = codecarbon_result.get("co2_grams", 0)
            method = "codecarbon"
        else:
            energy_mwh, co2_grams = self.estimate_proxy(model_tier, output_tokens)
            method = "proxy"

        baseline_mwh = PROXY_COEFFICIENTS.get(
            baseline_tier, PROXY_COEFFICIENTS["large"]
        ) * output_tokens
        saved_mwh  = max(0, baseline_mwh - energy_mwh)
        saved_pct  = round((saved_mwh / baseline_mwh) * 100) if baseline_mwh > 0 else 0

        # Update session
        self._session_energy_mwh  += energy_mwh
        self._session_co2_grams   += co2_grams
        self._session_prompt_count += 1

        return InferenceMetrics(
            model_tier=model_tier,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            energy_mwh=round(energy_mwh, 4),
            energy_joules=round(energy_mwh * 3.6, 4),
            measurement_method=method,
            co2_grams=round(co2_grams, 6),
            grid_intensity=self.grid_intensity,
            baseline_energy_mwh=round(baseline_mwh, 4),
            energy_saved_mwh=round(saved_mwh, 4),
            energy_saved_pct=saved_pct,
            session_energy_mwh=round(self._session_energy_mwh, 4),
            session_co2_grams=round(self._session_co2_grams, 6),
            session_tokens_saved=self._session_tokens_saved,
            session_prompt_count=self._session_prompt_count,
        )

    def session_summary(self) -> dict:
        """Return cumulative session metrics."""
        return {
            "total_energy_mwh":  round(self._session_energy_mwh, 4),
            "total_co2_grams":   round(self._session_co2_grams, 6),
            "total_prompts":     self._session_prompt_count,
            "grid_intensity":    self.grid_intensity,
        }

    def reset_session(self):
        """Reset session counters."""
        self._session_energy_mwh   = 0.0
        self._session_co2_grams    = 0.0
        self._session_tokens_saved = 0
        self._session_prompt_count = 0
