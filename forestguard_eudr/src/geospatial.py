"""Geospatial helpers. All area calculations use a projected CRS.

Rule enforced here: hectares are NEVER computed from geographic degrees.
"""
from __future__ import annotations

import math

import geopandas as gpd
from shapely.geometry.base import BaseGeometry


def utm_epsg_for(lon: float, lat: float) -> int:
    """Return the EPSG code of the UTM zone containing the point."""
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    return (32700 if lat < 0 else 32600) + zone


def to_projected(gdf: gpd.GeoDataFrame, epsg: int | None = None) -> gpd.GeoDataFrame:
    """Reproject to a metric CRS (auto-UTM by default) for area maths."""
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS; refusing to guess.")
    if epsg is None:
        c = gdf.unary_union.centroid
        epsg = utm_epsg_for(c.x, c.y)
    return gdf.to_crs(epsg=epsg)


def compute_area_ha(geom: BaseGeometry, target_epsg: int) -> float:
    """Area of a WGS-84 geometry in hectares, via reprojection."""
    if geom is None or geom.is_empty:
        return 0.0
    gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326").to_crs(epsg=target_epsg)
    return float(gdf.geometry.iloc[0].area) / 10_000.0


def validate_crs(gdf: gpd.GeoDataFrame, expected: str = "EPSG:4326") -> gpd.GeoDataFrame:
    """Normalise a GeoDataFrame to the expected CRS (default WGS-84)."""
    if gdf.crs is None:
        raise ValueError("Input GeoDataFrame has no CRS.")
    return gdf.to_crs(expected)
