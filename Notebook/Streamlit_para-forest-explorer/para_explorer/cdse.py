"""Copernicus Data Space Ecosystem - Sentinel-2 L2A availability for the AOI (public STAC search).

Used as *context* for the Planet analysis: how many free, 10 m Sentinel-2 scenes would exist for the
same place and period, and how cloudy are they? Search needs no credentials.
"""
from __future__ import annotations

import pandas as pd
import requests

from . import config as C


class CdseError(RuntimeError):
    pass


def s2_items(start: str, end: str, max_cloud: float = 100, max_pages: int = 20) -> tuple[pd.DataFrame, bool]:
    """Sentinel-2 L2A items intersecting the AOI -> DataFrame[id, datetime, cloud] (+ truncated flag)."""
    url = f"{C.CDSE_STAC_URL}/search"
    body = {"collections": [C.CDSE_S2_COLLECTION], "intersects": C.AOI_GEOMETRY, "limit": 100,
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z"}
    rows, truncated, req = [], False, ("POST", url, body)
    try:
        for page in range(max_pages):
            method, href, payload = req
            r = requests.post(href, json=payload, timeout=60) if method == "POST" else requests.get(href, timeout=60)
            if r.status_code >= 400:
                raise CdseError(f"CDSE STAC returned HTTP {r.status_code}.")
            js = r.json()
            for f in js.get("features", []):
                p = f.get("properties", {})
                rows.append({"id": f.get("id"), "datetime": p.get("datetime"), "cloud": p.get("eo:cloud_cover")})
            nxt = next((l for l in js.get("links", []) if l.get("rel") == "next"), None)
            if not nxt:
                break
            if page == max_pages - 1:
                truncated = True
                break
            if nxt.get("method", "GET").upper() == "POST":
                req = ("POST", nxt["href"], {**body, **(nxt.get("body") or {})})
            else:
                req = ("GET", nxt["href"], None)
    except requests.RequestException as e:
        raise CdseError(f"Could not reach the Copernicus Data Space Ecosystem: {e}") from e
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["id", "datetime", "cloud"]), truncated
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"])
    if max_cloud < 100:
        df = df[df["cloud"].fillna(100) <= max_cloud]
    return df.reset_index(drop=True), truncated


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"start": pd.to_datetime([], utc=True), "count": []})
    g = df.groupby(df["datetime"].dt.strftime("%Y-%m")).size()
    return pd.DataFrame({"start": pd.to_datetime(g.index + "-01", utc=True), "count": g.values})
