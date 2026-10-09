"""Data access layer. The UI never touches files directly.

Sample mode reads the bundled synthetic dataset; Planet mode is routed
through the planet_client adapter and falls back to sample mode on any
failure (offline demo guarantee).
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from .config import DATA_DIR
from .validation import validate_measurements, validate_plots
from .geospatial import to_projected


def load_suppliers(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_csv(data_dir / "suppliers.csv")


def load_plots(data_dir: Path = DATA_DIR) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(data_dir / "plots.geojson")
    gdf = validate_plots(gdf)
    # Hectares via UTM 22S (Pará). Never from degrees.
    gdf["area_ha"] = (to_projected(gdf).geometry.area / 10_000.0).round(1)
    return gdf


def load_measurements(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return validate_measurements(pd.read_csv(data_dir / "measurements.csv"))


def load_evidence(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_csv(data_dir / "evidence.csv")


def build_risk_table(plots: gpd.GeoDataFrame, measurements: pd.DataFrame,
                     baseline_year: int, comparison_year: int,
                     thresholds) -> pd.DataFrame:
    """Run summarise -> detect_change -> risk score for every plot.
    Returns a flat DataFrame ready for maps, charts and CSV export."""
    from .metrics import detect_change, summarize_plot
    from .risk_scoring import compute_risk_score

    rows = []
    for _, plot in plots.iterrows():
        summary = summarize_plot(measurements, plot["plot_id"],
                                 baseline_year, comparison_year)
        change = detect_change(summary, thresholds)
        score = compute_risk_score(summary, change, plot.to_dict(), thresholds)
        rows.append({
            **{k: plot[k] for k in ("plot_id", "supplier_id", "supplier_name",
                                    "commodity", "country", "area_ha",
                                    "legality_document_available",
                                    "certification_available", "scenario")},
            **summary, **{f"flag_{k}": v for k, v in change.items()
                          if isinstance(v, (bool, str, int, float))},
            "alert_types": ", ".join(change["alert_types"]),
            "confidence": change["confidence"],
            "recommended_action": change["recommended_action"],
            "risk_score": score.total,
            "risk_category": score.category,
            "is_alert": score.is_alert,
            "risk_breakdown": str(score.breakdown()),
        })
    return pd.DataFrame(rows)
