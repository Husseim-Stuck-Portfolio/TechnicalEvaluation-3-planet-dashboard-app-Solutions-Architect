"""Raster I/O and per-composite derivatives (NDVI, RGB preview, PNG overlays).

Input contract = the GeoTIFFs produced in notebook 3: 4 bands (blue, green, red, NIR),
float32, EPSG:4326, one file per period (``composite_2021.tif`` ... ``composite_All_years.tif``).

Design notes
------------
* NDVI is a ratio, so it is independent of the DN scale (ARPS: reflectance = DN / 10000).
* Full-resolution arrays are only used for the *numbers* (areas, histograms, patches). Anything
  drawn on a map/chart is block-averaged to <= ``max_px`` first - the browser never receives a
  2400 x 2400 raster.
"""
from __future__ import annotations

import base64
import io
import warnings
from pathlib import Path

import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from rasterio.enums import Resampling

from . import config as C
from . import theme as T

NDVI_CMAP = LinearSegmentedColormap.from_list("ndvi_green", T.NDVI_RAMP)
CHANGE_CMAP = LinearSegmentedColormap.from_list("change_div", T.CHANGE_RAMP)


# ----------------------------------------------------------------------------------------- #
# Reading
# ----------------------------------------------------------------------------------------- #
def raw_composite_path(folder: Path, name: str) -> Path:
    return Path(folder) / f"composite_{name.replace(' ', '_')}.tif"


def read_bands(path: Path, bands: list[int], max_px: int | None = None) -> np.ndarray:
    """Read 1-based ``bands`` as float32; optionally decimated with area-averaging."""
    with rasterio.open(path) as src:
        if max_px and max(src.height, src.width) > max_px:
            f = max(src.height, src.width) / max_px
            shape = (len(bands), max(1, round(src.height / f)), max(1, round(src.width / f)))
            arr = src.read(bands, out_shape=shape, resampling=Resampling.average)
        else:
            arr = src.read(bands)
    return arr.astype("float32")


def raster_info(path: Path) -> dict:
    with rasterio.open(path) as src:
        return {"width": src.width, "height": src.height, "bands": src.count,
                "crs": str(src.crs), "bounds": tuple(src.bounds), "res": src.res,
                "nodata": src.nodata}


def ndvi_from_bands(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """(NIR - Red) / (NIR + Red); non-physical / empty pixels become NaN (never 'no change')."""
    den = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (nir - red) / den
    out[~np.isfinite(out) | (den <= 0)] = np.nan
    return np.clip(out, -1.0, 1.0).astype("float32")


def read_ndvi(raw_path: Path) -> np.ndarray:
    red, nir = read_bands(raw_path, [3, 4])
    return ndvi_from_bands(red, nir)


# ----------------------------------------------------------------------------------------- #
# Geometry helpers
# ----------------------------------------------------------------------------------------- #
def pixel_area_ha_by_row(height: int, bounds: tuple[float, float, float, float], width: int) -> np.ndarray:
    """Pixel area (ha) for every raster row of a north-up EPSG:4326 grid.

    Uses the standard WGS84 degree-length series so areas are metric even though the file is in
    degrees (a 'pixel count' is not an area).
    """
    west, south, east, north = bounds
    dlon, dlat = (east - west) / width, (north - south) / height
    lat = north - (np.arange(height) + 0.5) * dlat
    phi = np.radians(lat)
    m_lat = 111132.92 - 559.82 * np.cos(2 * phi) + 1.175 * np.cos(4 * phi)
    m_lon = 111412.84 * np.cos(phi) - 93.5 * np.cos(3 * phi)
    return (dlon * m_lon) * (dlat * m_lat) / 1e4


def downsample(a: np.ndarray, max_px: int) -> np.ndarray:
    """NaN-aware block mean to at most ``max_px`` on the long side (extent preserved)."""
    f = int(np.ceil(max(a.shape[-2:]) / max_px))
    if f <= 1:
        return a
    h, w = a.shape[-2:]
    ph, pw = (-h) % f, (-w) % f
    if a.ndim == 2:
        a = np.pad(a, ((0, ph), (0, pw)), constant_values=np.nan)
        b = a.reshape(a.shape[0] // f, f, a.shape[1] // f, f)
    else:
        a = np.pad(a, ((0, 0), (0, ph), (0, pw)), constant_values=np.nan)
        b = a.reshape(a.shape[0], a.shape[1] // f, f, a.shape[2] // f, f)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmean(b, axis=(2, 4))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(b, axis=(1, 3))


# ----------------------------------------------------------------------------------------- #
# Rendering
# ----------------------------------------------------------------------------------------- #
def rgb_limits(rgb: np.ndarray, lo: float = 2, hi: float = 98) -> list[tuple[float, float]]:
    """One 2-98 % stretch per band, computed once on the reference composite (as in notebook 3)
    and then reused for every period so colours are comparable between years."""
    lims = []
    for b in range(3):
        v = rgb[b][np.isfinite(rgb[b])][::10]
        l, h = (np.percentile(v, [lo, hi]) if v.size else (0.0, 1.0))
        lims.append((float(l), float(h if h > l else l + 1e-6)))
    return lims


def to_rgba_uint8(bgr: np.ndarray, lims: list[tuple[float, float]]) -> np.ndarray:
    """(blue, green, red) float array -> HxWx4 uint8 (alpha = valid)."""
    chans = []
    for src_band in (2, 1, 0):  # R, G, B
        lo, hi = lims[src_band]
        chans.append(np.clip((bgr[src_band] - lo) / (hi - lo), 0, 1))
    valid = np.all(np.isfinite(np.stack(chans)), axis=0)
    rgb = np.nan_to_num(np.stack(chans, axis=-1), nan=0.0)
    out = np.dstack([(rgb * 255).astype("uint8"), (valid * 255).astype("uint8")])
    return out


def colorize(a: np.ndarray, cmap, vmin: float, vmax: float, alpha: np.ndarray | None = None) -> np.ndarray:
    """2-D float array -> HxWx4 uint8 using ``cmap``; NaN -> transparent."""
    norm = np.clip((a - vmin) / (vmax - vmin), 0, 1)
    rgba = cmap(np.nan_to_num(norm, nan=0.0), bytes=True)
    valid = np.isfinite(a)
    rgba[..., 3] = np.where(valid, 255 if alpha is None else (alpha * 255).astype("uint8"), 0)
    return rgba


def change_rgba(change: np.ndarray, vmin: float = -0.5, vmax: float = 0.5) -> np.ndarray:
    """Diverging map (red = decrease, blue = increase). Near-zero change is made transparent so
    the basemap shows through and only meaningful change draws the eye."""
    alpha = np.clip(np.abs(np.nan_to_num(change)) / 0.10, 0, 1) * 0.92
    return colorize(change, CHANGE_CMAP, vmin, vmax, alpha=alpha)


def ndvi_rgba(ndvi: np.ndarray) -> np.ndarray:
    return colorize(ndvi, NDVI_CMAP, *T.NDVI_RANGE)


def png_bytes(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def data_url(rgba: np.ndarray) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes(rgba)).decode()


def ndvi_stats(ndvi: np.ndarray) -> dict:
    v = ndvi[np.isfinite(ndvi)]
    if v.size == 0:
        return {"valid_pixels": 0, "mean": np.nan, "median": np.nan, "p05": np.nan, "p95": np.nan}
    p5, p50, p95 = np.percentile(v, [5, 50, 95])
    return {"valid_pixels": int(v.size), "mean": float(v.mean()), "median": float(p50),
            "p05": float(p5), "p95": float(p95)}
