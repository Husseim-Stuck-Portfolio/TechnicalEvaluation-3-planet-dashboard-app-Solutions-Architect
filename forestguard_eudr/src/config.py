"""Central configuration for ForestGuard EUDR.

All tunable analytical parameters live here so that the Streamlit UI, the
analytics engine and the unit tests share a single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "sample"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

APP_VERSION = "0.1.0"
APP_NAME = "ForestGuard EUDR"

# Regulation (EU) 2023/1115 benchmark: production must be deforestation-free
# relative to this date.
EUDR_CUTOFF_DATE = "2020-12-31"
EUDR_CUTOFF_YEAR = 2020

# ---------------------------------------------------------------- thresholds
@dataclass(frozen=True)
class Thresholds:
    """Screening thresholds. Exposed in the UI; every value is adjustable."""
    min_baseline_canopy_cover_percent: float = 30.0
    canopy_cover_loss_threshold_percent: float = 20.0
    minimum_affected_area_percent: float = 5.0
    carbon_loss_threshold_mg_per_ha: float = 20.0
    height_loss_threshold_m: float = 4.0
    risk_score_alert_threshold: float = 60.0
    # Reference declines that map to a component score of 100 (normalisation).
    reference_canopy_loss_percent: float = 50.0
    reference_carbon_loss_mg_ha: float = 80.0
    reference_height_loss_m: float = 15.0

DEFAULT_THRESHOLDS = Thresholds()

# ---------------------------------------------------------------- risk model
# Weights from the solution design; must sum to 100.
RISK_WEIGHTS: dict[str, float] = {
    "post_cutoff_canopy_loss": 30.0,
    "carbon_decline": 25.0,
    "carbon_decline_fix": 0.0,  # placeholder removed below
}
RISK_WEIGHTS = {
    "post_cutoff_canopy_loss": 30.0,
    "carbon_decline": 25.0,
    "height_decline": 15.0,
    "affected_area": 15.0,
    "regional_context": 5.0,
    "missing_evidence": 10.0,
}

# (lower_bound, upper_bound, label) - inclusive bounds, 0..100.
RISK_CATEGORIES: list[tuple[int, int, str]] = [
    (0, 24, "Low"),
    (25, 49, "Moderate"),
    (50, 74, "High"),
    (75, 100, "Critical"),
]

RISK_COLORS = {
    "Low": "#2ecc71",
    "Moderate": "#f1c40f",
    "High": "#e67e22",
    "Critical": "#c0392b",
}

# Demo heuristic: country-level deforestation-pressure context factor (0-100).
# Clearly documented as a configurable business heuristic, not a Planet product.
COUNTRY_CONTEXT_RISK: dict[str, float] = {
    "Brazil": 60.0,
    "Indonesia": 70.0,
    "Gabon": 30.0,
    "Democratic Republic of the Congo": 55.0,
    "default": 50.0,
}

# Measurement validity bounds (physical plausibility checks).
CANOPY_COVER_RANGE = (0.0, 100.0)
CANOPY_HEIGHT_RANGE = (0.0, 80.0)          # m; Amazon emergents rarely exceed ~60 m
CARBON_DENSITY_RANGE = (0.0, 400.0)        # Mg/ha
