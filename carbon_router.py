"""
GreenInfer Carbon Router
Fetches real-time electricity grid carbon intensity and adjusts
routing decisions to minimize carbon emissions.

Supports:
  - ElectricityMaps API (free tier available)
  - WattTime API
  - Static fallback with ERCOT Texas averages by hour
"""

import os
import time
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("greeninfer.carbon")

# ERCOT Texas hourly average carbon intensity (gCO2/kWh)
# Based on 2023 ERCOT generation mix data
# Higher at night/midday when coal is higher, lower during solar peak hours
ERCOT_HOURLY_AVERAGE = {
    0:  285, 1:  292, 2:  295, 3:  298, 4:  300, 5:  302,
    6:  295, 7:  275, 8:  245, 9:  210, 10: 185, 11: 168,
    12: 162, 13: 158, 14: 162, 15: 175, 16: 192, 17: 215,
    18: 248, 19: 268, 20: 278, 21: 282, 22: 284, 23: 285
}

# Routing policy thresholds (gCO2/kWh)
GRID_THRESHOLDS = {
    "very_clean":  150,   # Mostly renewables - allow large models freely
    "clean":       220,   # Good mix - normal balanced routing
    "moderate":    320,   # More fossil fuel - prefer smaller models
    "heavy":       450,   # Mostly coal/gas - force eco mode
}


@dataclass
class GridStatus:
    intensity: float           # gCO2/kWh
    label: str                 # "Very Clean" / "Clean" / "Moderate" / "Heavy"
    recommended_mode: str      # "performance" / "balanced" / "eco" / "eco"
    source: str                # "electricitymaps" / "watttime" / "ercot_estimate"
    timestamp: float           # Unix timestamp of measurement
    percent_renewable: Optional[float] = None


class CarbonRouter:
    """
    Fetches real-time grid carbon intensity and recommends routing modes.
    
    When API keys are available, fetches live data.
    Falls back to ERCOT hourly averages when no API is configured.
    Results are cached for 15 minutes to avoid excessive API calls.
    
    Example:
        router = CarbonRouter(zone="US-TEX-ERCO")
        status = router.get_grid_status()
        print(status.intensity, "gCO2/kWh")
        print("Recommended mode:", status.recommended_mode)
    """

    CACHE_TTL = 900   # 15 minutes

    def __init__(
        self,
        zone: str = "US-TEX-ERCO",
        electricity_maps_key: str = None,
        watttime_user: str = None,
        watttime_pass: str = None,
    ):
        self.zone = zone
        self._em_key = electricity_maps_key or os.environ.get("ELECTRICITY_MAPS_KEY")
        self._wt_user = watttime_user or os.environ.get("WATTTIME_USER")
        self._wt_pass = watttime_pass or os.environ.get("WATTTIME_PASS")
        self._cache: Optional[GridStatus] = None
        self._cache_time: float = 0

    def get_grid_status(self) -> GridStatus:
        """
        Get current grid carbon intensity.
        Returns cached result if fresh enough.
        """
        now = time.time()
        if self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        status = None

        # Try ElectricityMaps first
        if self._em_key:
            status = self._fetch_electricity_maps()

        # Try WattTime second
        if status is None and self._wt_user:
            status = self._fetch_watttime()

        # Fall back to ERCOT hourly average
        if status is None:
            status = self._ercot_estimate()

        self._cache = status
        self._cache_time = now
        return status

    def _fetch_electricity_maps(self) -> Optional[GridStatus]:
        """Fetch from ElectricityMaps API."""
        try:
            import httpx
            url = f"https://api.electricitymap.org/v3/carbon-intensity/latest?zone={self.zone}"
            headers = {"auth-token": self._em_key}
            r = httpx.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                intensity = float(data.get("carbonIntensity", 200))
                return GridStatus(
                    intensity=intensity,
                    label=self._label(intensity),
                    recommended_mode=self._mode(intensity),
                    source="electricitymaps",
                    timestamp=time.time()
                )
        except Exception as e:
            logger.warning(f"ElectricityMaps fetch failed: {e}")
        return None

    def _fetch_watttime(self) -> Optional[GridStatus]:
        """Fetch from WattTime API."""
        try:
            import httpx
            # Authenticate
            auth = httpx.get(
                "https://api2.watttime.org/v2/login",
                auth=(self._wt_user, self._wt_pass),
                timeout=5
            )
            if auth.status_code != 200:
                return None
            token = auth.json().get("token")
            r = httpx.get(
                "https://api2.watttime.org/v2/index",
                headers={"Authorization": f"Bearer {token}"},
                params={"ba": "ERCOT"},
                timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                # WattTime returns a 0-100 MOER index, convert to approx gCO2/kWh
                moer = float(data.get("percent", 50))
                intensity = 100 + (moer / 100) * 500
                return GridStatus(
                    intensity=intensity,
                    label=self._label(intensity),
                    recommended_mode=self._mode(intensity),
                    source="watttime",
                    timestamp=time.time()
                )
        except Exception as e:
            logger.warning(f"WattTime fetch failed: {e}")
        return None

    def _ercot_estimate(self) -> GridStatus:
        """Fall back to ERCOT hourly average for current hour."""
        from datetime import datetime
        hour = datetime.now().hour
        intensity = ERCOT_HOURLY_AVERAGE.get(hour, 220)
        logger.info(f"Using ERCOT hourly estimate for hour {hour}: {intensity} gCO2/kWh")
        return GridStatus(
            intensity=float(intensity),
            label=self._label(intensity),
            recommended_mode=self._mode(intensity),
            source="ercot_estimate",
            timestamp=time.time()
        )

    @staticmethod
    def _label(intensity: float) -> str:
        if intensity < GRID_THRESHOLDS["very_clean"]: return "Very Clean"
        if intensity < GRID_THRESHOLDS["clean"]:      return "Clean"
        if intensity < GRID_THRESHOLDS["moderate"]:   return "Moderate"
        if intensity < GRID_THRESHOLDS["heavy"]:      return "Heavy"
        return "Very Heavy"

    @staticmethod
    def _mode(intensity: float) -> str:
        if intensity < GRID_THRESHOLDS["very_clean"]: return "performance"
        if intensity < GRID_THRESHOLDS["clean"]:      return "balanced"
        if intensity < GRID_THRESHOLDS["moderate"]:   return "eco"
        return "eco"
