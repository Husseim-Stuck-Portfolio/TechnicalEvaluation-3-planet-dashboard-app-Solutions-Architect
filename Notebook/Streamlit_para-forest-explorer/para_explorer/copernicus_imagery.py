"""Sentinel-2 L2A image of the AOI from the Copernicus Data Space Ecosystem (Sentinel Hub Process API).

The request asks for the *same bounding box* as the Planet composites, in the same CRS (EPSG:4326) and on a square
pixel grid, so both datasets can be compared pixel by pixel. Clouds, cloud shadow, snow and saturated pixels are
removed with the scene-classification layer (SCL) and the per-pixel **median** of the remaining observations in the
time window is returned. Needs a free CDSE OAuth client (``CDSE_CLIENT_ID`` / ``CDSE_CLIENT_SECRET``).

Returned file layout (cached on disk, no credentials inside): float32 bands blue, green, red, nir (surface
reflectance 0-1) and a 0/1 validity band.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import composites as K
from . import config as C

SIZE = 1200                     # 1200 x 1200 px over ~24 km = ~18-20 m grid; keeps the request light
TIMEOUT = 180
GOOD_SCL = (4, 5, 6)            # vegetation, not-vegetated, water

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02", "B03", "B04", "B08", "SCL"], units: ["REFLECTANCE", "REFLECTANCE", "REFLECTANCE", "REFLECTANCE", "DN"] }],
    output: { bands: 5, sampleType: "FLOAT32" },
    mosaicking: "ORBIT"
  };
}
function median(a) { a.sort(function (x, y) { return x - y; }); var m = a.length >> 1; return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; }
function evaluatePixel(samples) {
  var ok = samples.filter(function (s) { return [4, 5, 6].indexOf(s.SCL) >= 0; });
  if (ok.length === 0) { return [0, 0, 0, 0, 0]; }
  return [median(ok.map(function (s) { return s.B02; })), median(ok.map(function (s) { return s.B03; })),
          median(ok.map(function (s) { return s.B04; })), median(ok.map(function (s) { return s.B08; })), 1];
}
"""


class CopernicusError(RuntimeError):
    pass


def window_for(period: str) -> tuple[str, str]:
    return C.COMPOSITE_WINDOWS.get(period, C.COMPOSITE_WINDOWS["All years"])


def cache_path(folder: Path, start: str, end: str, max_cloud: int, size: int = SIZE) -> Path:
    key = hashlib.sha1(f"{start}|{end}|{max_cloud}|{size}|{C.BBOX}".encode()).hexdigest()[:10]
    return Path(folder) / "copernicus" / f"s2_{start}_{end}_{key}.npz"


def token(client_id: str, client_secret: str, session: requests.Session | None = None) -> str:
    if not client_id or not client_secret:
        raise CopernicusError("Copernicus credentials are missing. Enter your CDSE OAuth client ID and secret "
                              "(or set CDSE_CLIENT_ID / CDSE_CLIENT_SECRET).")
    try:
        r = (session or requests).post(C.CDSE_TOKEN_URL, timeout=60, data={
            "grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret})
    except requests.Timeout as e:
        raise CopernicusError("The Copernicus login did not answer in time. Please try again.") from e
    except requests.RequestException as e:
        raise CopernicusError("Could not reach the Copernicus Data Space Ecosystem. Check your internet connection.") from e
    if r.status_code in (400, 401):
        raise CopernicusError("Copernicus rejected the OAuth client ID / secret.")
    if r.status_code == 403:
        raise CopernicusError("This Copernicus client is not allowed to use the Process API.")
    if r.status_code >= 400:
        raise CopernicusError(f"Copernicus login failed (HTTP {r.status_code}).")
    return r.json()["access_token"]


def request_body(start: str, end: str, max_cloud: int, size: int = SIZE) -> dict:
    w, s, e, n = C.BBOX
    return {
        "input": {
            "bounds": {"bbox": [w, s, e, n], "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": "sentinel-2-l2a",
                      "dataFilter": {"timeRange": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
                                     "maxCloudCoverage": int(max_cloud)}}],
        },
        "output": {"width": size, "height": size, "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
        "evalscript": EVALSCRIPT,
    }


def parse_tiff(content: bytes) -> dict:
    """GeoTIFF bytes -> {'bands': (4,h,w) float32 [B,G,R,NIR], 'valid': (h,w) bool}."""
    from rasterio.io import MemoryFile
    try:
        with MemoryFile(content) as mem, mem.open() as src:
            if src.count < 5:
                raise CopernicusError("Unexpected response from Copernicus (not a 5-band image).")
            arr = src.read().astype("float32")
    except CopernicusError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CopernicusError("Copernicus returned data that could not be read as an image.") from e
    valid = (arr[4] > 0.5) & np.all(np.isfinite(arr[:4]), axis=0) & (arr[:4].sum(axis=0) > 0)
    return {"bands": arr[:4], "valid": valid}


def fetch(client_id: str, client_secret: str, start: str, end: str, max_cloud: int = 70, size: int = SIZE,
          session: requests.Session | None = None) -> dict:
    """Download the cloud-masked median Sentinel-2 image for the AOI. Raises ``CopernicusError`` with a friendly message."""
    tok = token(client_id, client_secret, session)
    try:
        r = (session or requests).post(C.CDSE_PROCESS_URL, json=request_body(start, end, max_cloud, size), timeout=TIMEOUT,
                                       headers={"Authorization": f"Bearer {tok}", "Accept": "image/tiff"})
    except requests.Timeout as e:
        raise CopernicusError("Copernicus took too long to answer. Try a shorter date range and run it again.") from e
    except requests.RequestException as e:
        raise CopernicusError("Could not reach the Copernicus Data Space Ecosystem. Check your internet connection.") from e
    if r.status_code == 401:
        raise CopernicusError("Copernicus rejected the access token (HTTP 401).")
    if r.status_code == 403:
        raise CopernicusError("This Copernicus account has no access to the requested data (HTTP 403).")
    if r.status_code == 429:
        raise CopernicusError("Copernicus rate limit reached (HTTP 429). Wait a minute and retry.")
    if r.status_code >= 400:
        try:
            detail = r.json().get("error", {}).get("message", "")[:200]
        except ValueError:
            detail = ""
        raise CopernicusError(f"Copernicus could not process the request (HTTP {r.status_code}). {detail}".strip())
    return parse_tiff(r.content)


# ---------------------------------------------------------------------------------- cache -----
def save(scene: dict, path: Path, meta: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, bands=scene["bands"].astype("float16"), valid=scene["valid"], meta=json.dumps(meta))


def load(path: Path) -> tuple[dict, dict] | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        z = np.load(path, allow_pickle=False)
        return {"bands": z["bands"].astype("float32"), "valid": z["valid"].astype(bool)}, json.loads(str(z["meta"]))
    except Exception:  # noqa: BLE001 - a damaged cache file is simply ignored
        return None


# ------------------------------------------------------------------------------- derived -----
def ndvi(scene: dict) -> np.ndarray:
    out = K.ndvi_from_bands(scene["bands"][2], scene["bands"][3])
    out[~scene["valid"]] = np.nan
    return out


def rgb(scene: dict, lims=None) -> np.ndarray:
    """True colour uint8 (h, w, 3) with a 2-98 % stretch computed on this scene."""
    b = scene["bands"][:3].copy()
    b[:, ~scene["valid"]] = np.nan
    lims = lims or K.rgb_limits(b)
    return K.to_rgba_uint8(b, lims)[..., :3]


def ndvi_summary(nd: np.ndarray) -> dict:
    v = nd[np.isfinite(nd)]
    if v.size == 0:
        return {"mean": np.nan, "min": np.nan, "max": np.nan, "valid_pct": 0.0}
    return {"mean": float(v.mean()), "min": float(v.min()), "max": float(v.max()), "valid_pct": 100 * v.size / nd.size}


def pixel_size_m(shape: tuple[int, int]) -> tuple[float, float]:
    """(east-west, north-south) pixel size in metres of the AOI on a grid of ``shape`` (rows, cols)."""
    w, s, e, n = C.BBOX
    lat = np.radians((s + n) / 2)
    return ((e - w) / shape[1] * 111412.84 * np.cos(lat), (n - s) / shape[0] * 111132.92)


def compare(planet_nd: np.ndarray, cop_nd: np.ndarray) -> dict:
    """Pixel-wise agreement on the common grid (both arrays must have the same shape)."""
    if planet_nd.shape != cop_nd.shape:
        raise ValueError("Planet and Copernicus NDVI must be on the same grid.")
    both = np.isfinite(planet_nd) & np.isfinite(cop_nd)
    if both.sum() < 10:
        return {"n": int(both.sum()), "r": np.nan, "bias": np.nan, "rmse": np.nan}
    a, b = planet_nd[both], cop_nd[both]
    return {"n": int(both.sum()), "r": float(np.corrcoef(a, b)[0, 1]), "bias": float((a - b).mean()),
            "rmse": float(np.sqrt(np.mean((a - b) ** 2)))}


def stac_dates(start: str, end: str, max_cloud: float) -> dict:
    """Date range / number of Sentinel-2 scenes (public STAC) behind the comparison window. Never raises."""
    from . import cdse
    try:
        df, _ = cdse.s2_items(start, end, max_cloud)
    except Exception:  # noqa: BLE001
        return {}
    if df.empty:
        return {"n": 0}
    return {"n": int(len(df)), "first": df["datetime"].min().strftime("%Y-%m-%d"), "last": df["datetime"].max().strftime("%Y-%m-%d")}


def table(period: str, planet_nd: np.ndarray, planet_valid_pct: float, planet_dates: str, cop_nd: np.ndarray | None,
          cop_dates: str, grid_shape: tuple[int, int], planet_native_shape: tuple[int, int]) -> pd.DataFrame:
    """The Planet-vs-Copernicus metric table (strings, ready to display / export)."""
    pn = ndvi_summary(planet_nd)
    cn = ndvi_summary(cop_nd) if cop_nd is not None else None
    g = pixel_size_m(grid_shape)
    pp = pixel_size_m(planet_native_shape)
    f = lambda v, fmt: "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)  # noqa: E731
    rows = [
        ("Mean NDVI", f(pn["mean"], "{:.3f}"), f(cn and cn["mean"], "{:.3f}") if cn else "not loaded"),
        ("Minimum NDVI", f(pn["min"], "{:.3f}"), f(cn and cn["min"], "{:.3f}") if cn else "not loaded"),
        ("Maximum NDVI", f(pn["max"], "{:.3f}"), f(cn and cn["max"], "{:.3f}") if cn else "not loaded"),
        ("Valid pixels", f(planet_valid_pct, "{:.1f} %"), f(cn and cn["valid_pct"], "{:.1f} %") if cn else "not loaded"),
        ("Spatial resolution", f"≈{pp[0]:.0f} m composite grid (source PlanetScope ≈3 m)",
         "10 m native bands (B02, B03, B04, B08)"),
        ("Compared on", f"{grid_shape[1]}×{grid_shape[0]} px grid (≈{g[0]:.0f} m)", f"{grid_shape[1]}×{grid_shape[0]} px grid (≈{g[0]:.0f} m)"),
        ("Period", planet_dates, cop_dates),
        ("Projection", "EPSG:4326 (WGS 84)", "EPSG:4326 (WGS 84), requested on the same bounding box"),
        ("Bands", "Blue, Green, Red, NIR (PlanetScope surface reflectance)", "B02, B03, B04, B08 (Sentinel-2 L2A surface reflectance)"),
        ("Processing", "Annual composite built in notebook 2/3", "Per-pixel median of cloud-masked scenes (SCL)"),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Planet", "Copernicus"])
