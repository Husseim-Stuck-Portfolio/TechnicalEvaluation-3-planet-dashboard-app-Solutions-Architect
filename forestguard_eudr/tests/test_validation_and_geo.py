import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from src.geospatial import compute_area_ha, utm_epsg_for
from src.validation import (check_measurements_exist, validate_measurements,
                            validate_plots)


def test_utm_zone_para():
    assert utm_epsg_for(-52.37, -6.77) == 32722


def test_area_ha_from_degrees():
    # 1 km x 1 km near the Pará demo centre (~100 ha)
    geom = box(-52.375, -6.775, -52.365, -6.765)
    ha = compute_area_ha(geom, 32722)
    assert ha == pytest.approx(123.0, rel=0.05)  # cos(lat) scaling, ~1.23 km^2


def test_validate_plots_rejects_duplicates():
    g = box(-52.4, -6.8, -52.39, -6.79)
    gdf = gpd.GeoDataFrame(
        {"plot_id": ["A", "A"], "supplier_id": ["S1", "S1"],
         "supplier_name": ["n", "n"], "commodity": ["soy", "soy"],
         "country": ["Brazil", "Brazil"]},
        geometry=[g, g], crs="EPSG:4326")
    with pytest.raises(ValueError):
        validate_plots(gdf)


def test_validate_plots_rejects_invalid_geometry():
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame(
        {"plot_id": ["A"], "supplier_id": ["S1"], "supplier_name": ["n"],
         "commodity": ["soy"], "country": ["Brazil"]},
        geometry=[bowtie], crs="EPSG:4326")
    with pytest.raises(ValueError):
        validate_plots(gdf)


def test_validate_measurements_range():
    df = pd.DataFrame({
        "plot_id": ["A"], "year": [2020],
        "canopy_cover_percent": [120.0], "canopy_height_m": [10.0],
        "carbon_density_mg_ha": [50.0], "data_source": ["t"],
    })
    with pytest.raises(ValueError):
        validate_measurements(df)


def test_check_measurements_exist():
    df = pd.DataFrame({"plot_id": ["A"], "year": [2019]})
    with pytest.raises(ValueError):
        check_measurements_exist(df, "A", 2019, 2020)
