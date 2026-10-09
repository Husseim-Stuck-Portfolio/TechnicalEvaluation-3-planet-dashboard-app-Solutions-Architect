"""Input validation. Fails loudly with actionable messages, never silently.

Every public function returns a cleaned object or raises ValueError with a
message the UI can surface to the user.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from .config import CANOPY_COVER_RANGE, CANOPY_HEIGHT_RANGE, CARBON_DENSITY_RANGE

PLOT_REQUIRED_COLUMNS = {
    "plot_id", "supplier_id", "supplier_name", "commodity", "country",
}
MEASUREMENT_REQUIRED_COLUMNS = {
    "plot_id", "year", "canopy_cover_percent", "canopy_height_m",
    "carbon_density_mg_ha", "data_source",
}


def validate_plots(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Check schema, geometry validity and id uniqueness. Returns cleaned gdf."""
    missing = PLOT_REQUIRED_COLUMNS - set(gdf.columns)
    if missing:
        raise ValueError(f"plots missing required columns: {sorted(missing)}")
    if gdf.crs is None:
        raise ValueError("plots GeoDataFrame must carry a CRS (EPSG:4326 expected).")
    if gdf["plot_id"].duplicated().any():
        dupes = gdf.loc[gdf["plot_id"].duplicated(), "plot_id"].tolist()
        raise ValueError(f"duplicate plot_id values: {dupes}")
    bad_geom = ~gdf.geometry.is_valid | gdf.geometry.is_empty
    if bad_geom.any():
        ids = gdf.loc[bad_geom, "plot_id"].tolist()
        raise ValueError(f"invalid or empty geometries for plot_id: {ids}")
    if gdf["supplier_id"].isna().any():
        raise ValueError("plots with missing supplier_id are not allowed.")
    return gdf


def validate_measurements(df: pd.DataFrame) -> pd.DataFrame:
    """Check schema, value plausibility and completeness. Returns cleaned df."""
    missing = MEASUREMENT_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"measurements missing required columns: {sorted(missing)}")
    if df["plot_id"].isna().any() or df["year"].isna().any():
        raise ValueError("measurements require non-null plot_id and year.")
    for col, (lo, hi) in {
        "canopy_cover_percent": CANOPY_COVER_RANGE,
        "canopy_height_m": CANOPY_HEIGHT_RANGE,
        "carbon_density_mg_ha": CARBON_DENSITY_RANGE,
    }.items():
        if (df[col] < lo).any() or (df[col] > hi).any():
            raise ValueError(f"{col} outside physical range [{lo}, {hi}].")
    return df


def check_year_order(baseline_year: int, comparison_year: int) -> None:
    if comparison_year <= baseline_year:
        raise ValueError(
            f"comparison year ({comparison_year}) must be after "
            f"baseline year ({baseline_year})."
        )


def check_measurements_exist(df: pd.DataFrame, plot_id: str,
                             baseline_year: int, comparison_year: int) -> None:
    sub = df[df["plot_id"] == plot_id]
    for year in (baseline_year, comparison_year):
        if not (sub["year"] == year).any():
            raise ValueError(f"plot {plot_id}: no measurement for year {year}.")
