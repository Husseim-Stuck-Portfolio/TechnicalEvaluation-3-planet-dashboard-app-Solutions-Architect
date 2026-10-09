"""Generate deterministic synthetic sample data for the Pará demo AOI.

IMPORTANT: every record is SYNTHETIC demo data, not real Planet measurements.
Scenarios intentionally cover all dashboard states: stable forest,
post-cutoff clearing, gradual degradation, long-converted agriculture, and
suppliers with missing legality evidence.

Run:  python scripts/generate_sample_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DATA_DIR  # noqa: E402

SEED = 42
rng = np.random.default_rng(SEED)

AOI_CENTER = (-52.37, -6.77)          # Pará sandbox region (lon, lat)
YEARS = list(range(2015, 2024))
N_PLOTS = 24

SUPPLIERS = [
    ("SUP-001", "AgroExport do Pará Ltda", "soy"),
    ("SUP-002", "Verde Xingu Trading", "soy"),
    ("SUP-003", "Amazônia Agri Coop", "cocoa"),
    ("SUP-004", "Rio Fresco Holdings", "soy"),
    ("SUP-005", "São Félix Cerrado Farms", "cattle"),
]

# 6 stable forest, 7 post-cutoff clearing, 5 gradual degradation,
# 4 long-converted agriculture, 2 recovering/degraded secondary.
SCENARIOS = (["stable_forest"] * 5 + ["post_cutoff_clearing"] * 7
             + ["gradual_degradation"] * 4 + ["agriculture"] * 4
             + ["secondary_growth"] * 2 + ["selective_logging"] * 2)

# Suppliers SUP-003 and SUP-005 ship some plots without legality documents.
MISSING_DOCS_SUPPLIERS = {"SUP-003", "SUP-005"}


def make_plot_geometries(n: int) -> list:
    """Rectangles in UTM 22S (EPSG:32722) so hectares are exact, then to WGS-84."""
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32722", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:32722", "EPSG:4326", always_xy=True)
    cx, cy = to_utm.transform(*AOI_CENTER)
    geoms = []
    placed = []
    attempts = 0
    while len(geoms) < n and attempts < 5000:
        attempts += 1
        w = rng.uniform(350, 1200)          # meters
        h = rng.uniform(350, 1200)
        x0 = cx + rng.uniform(-15_000, 15_000)
        y0 = cy + rng.uniform(-12_000, 12_000)
        rect = box(x0, y0, x0 + w, y0 + h)
        if all(rect.distance(p) > 150 for p in placed):   # keep plots separable
            placed.append(rect)
            geoms.append(box(*to_wgs.transform(rect.bounds[0], rect.bounds[1]),
                             *to_wgs.transform(rect.bounds[2], rect.bounds[3])))
    return geoms


def canopy_series(scenario: str) -> np.ndarray:
    """Annual canopy cover % 2015-2023 per scenario, with noise."""
    n = len(YEARS)
    if scenario == "stable_forest":
        base = rng.uniform(72, 90)
        s = base + rng.normal(0, 2.5, n)
    elif scenario == "post_cutoff_clearing":
        base = rng.uniform(65, 85)
        s = base + rng.normal(0, 2.0, n)
        # sharp drop strictly AFTER the EUDR cutoff (2021 onwards) so the
        # post-cutoff screening logic is exercised unambiguously
        s[6] = base * rng.uniform(0.45, 0.6)   # 2021: first clearing year
        s[7:] = rng.uniform(4, 18) + rng.normal(0, 1.5, n - 7)
    elif scenario == "gradual_degradation":
        base = rng.uniform(60, 80)
        drift = -np.linspace(0, rng.uniform(18, 30), n)
        s = base + drift + rng.normal(0, 2.0, n)
    elif scenario == "selective_logging":
        # mild post-cutoff disturbance: partial canopy/carbon dip, forest persists
        base = rng.uniform(68, 82)
        s = base + rng.normal(0, 2.0, n)
        dip = rng.uniform(18, 26)
        s[7] = base - dip * 0.6    # 2022
        s[8] = base - dip          # 2023
    elif scenario == "secondary_growth":
        base = rng.uniform(45, 58)
        drift = np.linspace(-rng.uniform(6, 10), rng.uniform(2, 6), n)
        s = base + drift + rng.normal(0, 2.0, n)
    else:  # agriculture: long-converted, always below forest threshold
        s = rng.uniform(5, 16) + rng.normal(0, 1.5, n)
    return np.clip(s, 0, 100)


def dependent_series(canopy: np.ndarray, height_at_70m: float,
                     carbon_at_70m: float) -> tuple[np.ndarray, np.ndarray]:
    """Height (m) and carbon density (Mg/ha) as noisy functions of canopy."""
    height = height_at_70m * (canopy / 70.0) ** 0.6 + rng.normal(0, 1.2, len(canopy))
    carbon = carbon_at_70m * (canopy / 70.0) ** 1.3 + rng.normal(0, 6, len(canopy))
    return np.clip(height, 0, 80), np.clip(carbon, 0, 400)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    geoms = make_plot_geometries(N_PLOTS)
    rng.shuffle(SCENARIOS)

    suppliers_rows, plots_rows, meas_rows, evid_rows = [], [], [], []
    for i, (geom, scenario) in enumerate(zip(geoms, SCENARIOS)):
        sup_id, sup_name, commodity = SUPPLIERS[i % len(SUPPLIERS)]
        plot_id = f"PLT-{i+1:03d}"
        missing_docs = sup_id in MISSING_DOCS_SUPPLIERS and rng.random() < 0.5

        suppliers_rows.append({
            "supplier_id": sup_id, "supplier_name": sup_name,
            "country": "Brazil", "commodity": commodity,
            "contact": f"compliance@{sup_id.lower().replace('-', '')}.example.com",
            "supplier_status": "active",
        })
        plots_rows.append({
            "plot_id": plot_id, "supplier_id": sup_id, "supplier_name": sup_name,
            "commodity": commodity, "country": "Brazil",
            "production_start_date": f"20{rng.integers(10, 22)}-0{rng.integers(1, 9)}-15",
            "production_end_date": "ongoing",
            "legality_document_available": not missing_docs,
            "certification_available": bool(rng.random() < 0.4),
            "scenario": scenario,                     # transparent demo label
            "geometry": geom,
        })

        canopy = canopy_series(scenario)
        h70, c70 = rng.uniform(26, 34), rng.uniform(150, 220)
        height, carbon = dependent_series(canopy, h70, c70)
        for j, year in enumerate(YEARS):
            meas_rows.append({
                "plot_id": plot_id, "year": year,
                "canopy_cover_percent": round(float(canopy[j]), 1),
                "canopy_height_m": round(float(height[j]), 1),
                "carbon_density_mg_ha": round(float(carbon[j]), 1),
                "data_source": "synthetic_demo",
                "product_version": "SYNTHETIC-1.0",
                "data_quality_flag": "ok",
            })

        evid_rows.append({
            "plot_id": plot_id, "evidence_type": "legality_document",
            "file_name": None if missing_docs else f"legality_{plot_id}.pdf",
            "source": "supplier_upload", "collection_date": "2023-06-30",
            "review_status": "pending" if missing_docs else "reviewed",
            "reviewer": None if missing_docs else "compliance.team@example.com",
            "notes": "missing - requested from supplier" if missing_docs else "",
        })

    gpd.GeoDataFrame(plots_rows, crs="EPSG:4326").to_file(
        DATA_DIR / "plots.geojson", driver="GeoJSON")
    pd.DataFrame(suppliers_rows).drop_duplicates("supplier_id").to_csv(
        DATA_DIR / "suppliers.csv", index=False)
    pd.DataFrame(meas_rows).to_csv(DATA_DIR / "measurements.csv", index=False)
    pd.DataFrame(evid_rows).to_csv(DATA_DIR / "evidence.csv", index=False)
    print(f"sample data written to {DATA_DIR} "
          f"({len(plots_rows)} plots, {len(meas_rows)} measurements)")


if __name__ == "__main__":
    main()
