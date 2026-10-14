"""Optional user-supplied area of interest (GeoJSON) for the Planet / Copernicus queries."""
from __future__ import annotations

import json

MAX_BBOX_DEG = 2.0       # protects the APIs and the browser from continent-sized polygons


def _walk(c):
    if c and isinstance(c[0], (int, float)):
        yield c
    else:
        for i in c:
            yield from _walk(i)


def parse_geojson(raw: bytes | str) -> tuple[dict | None, str | None]:
    """-> (Polygon/MultiPolygon geometry, None) or (None, friendly error)."""
    try:
        gj = json.loads(raw)
    except (ValueError, TypeError):
        return None, "That file is not valid JSON."
    geom = gj
    if gj.get("type") == "FeatureCollection":
        feats = gj.get("features") or []
        geom = feats[0].get("geometry") if feats else None
    elif gj.get("type") == "Feature":
        geom = gj.get("geometry")
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        return None, "Please upload a GeoJSON with a Polygon or MultiPolygon."
    pts = list(_walk(geom.get("coordinates", [])))
    if len(pts) < 4:
        return None, "The polygon needs at least 3 distinct corners."
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    if not (-180 <= min(lons) and max(lons) <= 180 and -90 <= min(lats) and max(lats) <= 90):
        return None, "Coordinates must be longitude/latitude (EPSG:4326)."
    if max(lons) - min(lons) > MAX_BBOX_DEG or max(lats) - min(lats) > MAX_BBOX_DEG:
        return None, f"The area is larger than {MAX_BBOX_DEG:g}° x {MAX_BBOX_DEG:g}°; please upload a smaller polygon."
    return {"type": geom["type"], "coordinates": geom["coordinates"]}, None
