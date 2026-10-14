"""Planet Data API client (api.planet.com) - discovery only, never downloads imagery.

Design decisions (documented because they are API-constraint driven):

* **Stats API for charts.** ``/data/v1/stats`` returns server-side counts per month/year, so the
  bar charts stay exact and fast even when the AOI holds tens of thousands of scenes. Paging all
  scenes through quick-search just to count them would be slow and rate-limit-prone.
* **Quick-search for previews only**, newest/least-cloudy first, with a hard cap on pages.
* **Thumbnails are fetched per page on demand** with the user's key, kept in server memory
  (``st.cache_data``) and never written to disk or offered for download: the assets stay behind
  the API and the user's entitlement.
* Auth is HTTP Basic: key as username, empty password. The key is never logged or cached as a key.
* Errors are mapped to ``PlanetError`` with a message a user can act on (401/403/429/timeouts).
"""
from __future__ import annotations

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config as C

TIMEOUT = (10, 60)


class PlanetError(RuntimeError):
    pass


def _session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.auth = (api_key.strip(), "")
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 502, 503, 504),
                  allowed_methods=frozenset({"GET", "POST"}), respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def _check(r: requests.Response) -> requests.Response:
    if r.status_code == 401:
        raise PlanetError("Planet rejected the API key (HTTP 401). Check the key and try again.")
    if r.status_code == 403:
        raise PlanetError("The key is valid but has no access to this item type / data (HTTP 403).")
    if r.status_code == 429:
        raise PlanetError("Planet rate limit reached (HTTP 429). Wait a minute and retry.")
    if r.status_code >= 400:
        try:
            detail = r.json().get("message") or r.text[:200]
        except ValueError:
            detail = r.text[:200]
        raise PlanetError(f"Planet API error {r.status_code}: {detail}")
    return r


def build_filter(start: str, end: str, cloud_min: float, cloud_max: float,
                 scene_ids: list[str] | None = None, geometry: dict | None = None) -> dict:
    """AND of: AOI, acquired date range, cloud range (0-100 %, field ``cloud_percent``), optional ids."""
    cfg = [
        {"type": "GeometryFilter", "field_name": "geometry", "config": geometry or C.AOI_GEOMETRY},
        {"type": "DateRangeFilter", "field_name": "acquired",
         "config": {"gte": f"{start}T00:00:00Z", "lte": f"{end}T23:59:59Z"}},
        {"type": "RangeFilter", "field_name": "cloud_percent", "config": {"gte": cloud_min, "lte": cloud_max}},
    ]
    if scene_ids:
        cfg.append({"type": "StringInFilter", "field_name": "id", "config": scene_ids})
    return {"type": "AndFilter", "config": cfg}


def validate_key(api_key: str) -> bool:
    r = _session(api_key).get(f"{C.PLANET_DATA_URL}/item-types", timeout=TIMEOUT)
    _check(r)
    return True


def stats(api_key: str, item_types: list[str], flt: dict, interval: str = "month") -> pd.DataFrame:
    """Server-side counts per ``interval`` -> DataFrame[start (datetime), count]."""
    try:
        r = _session(api_key).post(f"{C.PLANET_DATA_URL}/stats", timeout=TIMEOUT,
                                   json={"interval": interval, "item_types": item_types, "filter": flt})
    except requests.RequestException as e:
        raise PlanetError(f"Could not reach Planet: {e}") from e
    js = _check(r).json()
    df = pd.DataFrame(js.get("buckets", []))
    if df.empty:
        return pd.DataFrame({"start": pd.to_datetime([], utc=True), "count": []})
    df["start"] = pd.to_datetime(df["start_time"], utc=True)
    return df[["start", "count"]].sort_values("start").reset_index(drop=True)


def search(api_key: str, item_types: list[str], flt: dict, sort: str = "acquired desc",
           page_size: int = 250, max_pages: int = 4) -> tuple[list[dict], bool]:
    """Quick-search with paging. Returns (features, truncated)."""
    s = _session(api_key)
    url = f"{C.PLANET_DATA_URL}/quick-search"
    params = {"_sort": sort, "_page_size": page_size}
    feats: list[dict] = []
    truncated = False
    try:
        r = s.post(url, params=params, json={"item_types": item_types, "filter": flt}, timeout=TIMEOUT)
        for page in range(max_pages):
            js = _check(r).json()
            feats += js.get("features", [])
            nxt = js.get("_links", {}).get("_next")
            if not nxt:
                break
            if page == max_pages - 1:
                truncated = True
                break
            r = s.get(nxt, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise PlanetError(f"Could not reach Planet: {e}") from e
    return feats, truncated


def to_frame(features: list[dict]) -> pd.DataFrame:
    rows = []
    for f in features:
        p, links = f.get("properties", {}), f.get("_links", {})
        cloud = p.get("cloud_percent")
        if cloud is None and p.get("cloud_cover") is not None:
            cloud = 100 * p["cloud_cover"]
        rows.append({"id": f.get("id"), "item_type": p.get("item_type") or f.get("item_type"),
                     "acquired": pd.to_datetime(p.get("acquired"), utc=True, errors="coerce"),
                     "cloud_percent": cloud, "quality": p.get("quality_category"),
                     "thumbnail": links.get("thumbnail"), "geometry": f.get("geometry")})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["year"] = df["acquired"].dt.year
        df["month"] = df["acquired"].dt.month
    return df


def thumbnail(api_key: str, url: str, width: int = 512) -> bytes:
    try:
        r = _session(api_key).get(url, params={"width": width}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise PlanetError(f"Preview unavailable: {e}") from e
    _check(r)
    if not r.headers.get("content-type", "").startswith("image"):
        raise PlanetError("Preview unavailable: unexpected response type.")
    return r.content


def monthly_from_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Offline fallback (CSV of notebook 1): same shape as ``stats(...)``."""
    if df.empty:
        return pd.DataFrame({"start": pd.to_datetime([], utc=True), "count": []})
    g = df.groupby(df["acquired"].dt.tz_convert("UTC").dt.strftime("%Y-%m")).size()
    out = pd.DataFrame({"start": pd.to_datetime(g.index + "-01", utc=True), "count": g.values})
    return out.sort_values("start").reset_index(drop=True)
