"""Streamlit-side service layer: cached loaders and API wrappers.

Rules of thumb used here (and worth defending in the review):
* big arrays  -> ``st.cache_resource`` (shared, never pickled/copied);
* small results (tables, GeoJSON, PNG data-URLs) -> ``st.cache_data`` keyed by the analysis parameters;
* anything touching the user's Planet key takes it as ``_key`` (not hashed into the cache key, so it
  is never stored as a key) plus a short SHA-256 fingerprint so different keys never share entries.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.colors import to_rgb

from . import analysis as A
from . import cdse
from . import composites as K
from . import config as C
from . import copernicus_imagery as CI
from . import figures as F
from . import planet
from . import store
from . import theme as T


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:12]


def stamp(folder: str | Path) -> float:
    m = Path(folder) / "meta.json"
    return m.stat().st_mtime if m.exists() else 0.0


# ----------------------------------------------------------------------------- composites -----
@st.cache_resource(show_spinner="Loading NDVI composites…")
def load_data(folder: str, mtime: float) -> dict:
    ndvis = store.load_ndvis(folder)
    meta = json.loads((Path(folder) / "meta.json").read_text())
    h, w = next(iter(ndvis.values())).shape
    bounds = tuple(meta["bounds"])
    return {"ndvis": ndvis, "meta": meta, "bounds": bounds, "shape": (h, w), "folder": folder,
            "area_row": K.pixel_area_ha_by_row(h, bounds, w)}


@st.cache_data(show_spinner=False)
def period_stats(folder: str, mtime: float) -> pd.DataFrame:
    d = load_data(folder, mtime)
    rows = []
    for name, nd in d["ndvis"].items():
        st_ = K.ndvi_stats(nd)
        rows.append({"period": name, "mean_ndvi": st_["mean"], "median_ndvi": st_["median"], "p05": st_["p05"],
                     "p95": st_["p95"], "valid_km2": st_["valid_pixels"] * float(d["area_row"].mean()) / 100})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def budget(folder: str, mtime: float, a: str, b: str, t_mod: float, t_strong: float) -> pd.DataFrame:
    d = load_data(folder, mtime)
    t_mod, t_strong, _ = C.validate_thresholds(t_mod, t_strong)
    return A.change_budget(d["ndvis"][a], d["ndvis"][b], d["area_row"], t_mod, t_strong)


@st.cache_data(show_spinner=False)
def histogram(folder: str, mtime: float, a: str, b: str):
    d = load_data(folder, mtime)
    return A.change_histogram(d["ndvis"][a], d["ndvis"][b])


@st.cache_data(show_spinner="Detecting decline patches…")
def patches(folder: str, mtime: float, a: str, b: str, thr: float, min_ha: float):
    d = load_data(folder, mtime)
    thr = C.clamp_threshold(thr, C.DEFAULT_T_STRONG)
    min_ha = max(0.0, float(min_ha))
    return A.detect_patches(d["ndvis"], a, b, thr, min_ha, d["area_row"], d["bounds"])


@st.cache_data(show_spinner="Computing trajectories…")
def trajectory(folder: str, mtime: float, tau: float):
    d = load_data(folder, mtime)
    tau = C.clamp_threshold(tau)
    nd = d["ndvis"]
    traj = A.trajectory(nd["2021"], nd["2022"], nd["2023"], tau)
    return A.trajectory_table(traj, d["area_row"]), K.downsample(traj.astype("float32"), 400).round().astype("uint8")


@st.cache_data(show_spinner="Running sensitivity grid…")
def sensitivity(folder: str, mtime: float, a: str, b: str):
    d = load_data(folder, mtime)
    return A.sensitivity(d["ndvis"][a], d["ndvis"][b], d["area_row"], (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40), C.SENS_MIN_HA)


@st.cache_data(show_spinner=False)
def small_ndvi(folder: str, mtime: float, period: str, px: int = 380) -> np.ndarray:
    return K.downsample(load_data(folder, mtime)["ndvis"][period], px)


@st.cache_data(show_spinner=False)
def small_change(folder: str, mtime: float, a: str, b: str, px: int = 380) -> np.ndarray:
    nd = load_data(folder, mtime)["ndvis"]
    return K.downsample(nd[b] - nd[a], px)


@st.cache_data(show_spinner=False)
def small_rgb(folder: str, mtime: float, period: str, px: int = 380) -> np.ndarray:
    rgba = store.load_rgba(folder, period)
    f = max(1, int(np.ceil(max(rgba.shape[:2]) / px)))
    return rgba[::f, ::f, :3]


@st.cache_data(show_spinner=False, max_entries=64)
def composite_png(folder: str, mtime: float, period: str, kind: str, style: str = "dark", subtitle: str = "", px: int = 900) -> bytes:
    """Square PNG of one composite ('rgb' | 'ndvi'); identical canvas for every period."""
    if kind == "rgb":
        rgba = store.load_rgba(folder, period)
        f = max(1, int(np.ceil(max(rgba.shape[:2]) / px)))
        data = rgba[::f, ::f, :3]
        title = f"{period} · true colour"
    else:
        data = K.downsample(load_data(folder, mtime)["ndvis"][period], px)
        title = f"{period} · NDVI"
    return F.to_png(F.composite_figure(kind, data, title, subtitle, style))


@st.cache_data(show_spinner=False, max_entries=24)
def change_png(folder: str, mtime: float, a: str, b: str, style: str = "dark", px: int = 900) -> bytes:
    nd = load_data(folder, mtime)["ndvis"]
    return F.to_png(F.composite_figure("change", K.downsample(nd[b] - nd[a], px), f"NDVI change {a} → {b}",
                                       "red = lower vegetation in the later period", style))


@st.cache_data(show_spinner="Rendering overlay…", max_entries=24)
def overlay_url(folder: str, mtime: float, kind: str, period: str, a: str, b: str, tau: float) -> str:
    """PNG data-URL for the globe. kind in {'rgb','ndvi','change','trajectory'}."""
    d = load_data(folder, mtime)
    nd = d["ndvis"]
    if kind == "rgb":
        return K.data_url(store.load_rgba(folder, period))
    if kind == "ndvi":
        return K.data_url(K.ndvi_rgba(K.downsample(nd[period], 1200)))
    if kind == "change":
        return K.data_url(K.change_rgba(K.downsample(nd[b] - nd[a], 1200)))
    if kind == "trajectory":
        traj = A.trajectory(nd["2021"], nd["2022"], nd["2023"], tau)
        f = int(np.ceil(max(traj.shape) / 1200))
        t = traj[::f, ::f]
        lut = np.zeros((6, 4), dtype=np.uint8)
        for k, (_, col) in T.TRAJECTORY.items():
            lut[k, :3] = [int(c * 255) for c in to_rgb(col)]
            lut[k, 3] = 0 if k in (0, 1) else 225   # 'stable' and 'no data' stay transparent
        return K.data_url(lut[t])
    raise ValueError(kind)


# --------------------------------------------------------------------------- Planet API -------
@st.cache_data(ttl=900, show_spinner="Asking Planet for counts…")
def planet_stats(_key: str, fp: str, item_types: tuple, flt_json: str, interval: str) -> pd.DataFrame:
    return planet.stats(_key, list(item_types), json.loads(flt_json), interval)


@st.cache_data(ttl=900, show_spinner="Searching Planet scenes…")
def planet_search(_key: str, fp: str, item_types: tuple, flt_json: str, sort: str, max_pages: int):
    return planet.search(_key, list(item_types), json.loads(flt_json), sort=sort, max_pages=max_pages)


@st.cache_data(ttl=1800, max_entries=300, show_spinner=False)
def planet_thumb(_key: str, fp: str, url: str, width: int) -> bytes:
    return planet.thumbnail(_key, url, width)


@st.cache_data(ttl=3600, show_spinner="Querying Copernicus Data Space…")
def cdse_items(start: str, end: str, max_cloud: float, geometry_json: str = ""):
    return cdse.s2_items(start, end, max_cloud, geometry=json.loads(geometry_json) if geometry_json else None)


# ------------------------------------------------------------------ Planet vs Copernicus -----
@st.cache_data(show_spinner=False, max_entries=8)
def planet_on_grid(folder: str, mtime: float, period: str, size: int = CI.SIZE):
    """(NDVI float32, true-colour uint8) of one Planet composite on the common ``size`` x ``size`` grid."""
    from PIL import Image
    nd = K.downsample(load_data(folder, mtime)["ndvis"][period], size)
    rgb = store.load_rgba(folder, period)[..., :3]
    if nd.shape != (size, size):
        nd = np.array(Image.fromarray(nd).resize((size, size), Image.BILINEAR))
    if rgb.shape[:2] != (size, size):
        rgb = np.array(Image.fromarray(rgb).resize((size, size), Image.BILINEAR))
    return nd, rgb


@st.cache_data(show_spinner=False)
def planet_dates(folder: str, mtime: float, period: str) -> str:
    """'2021-01-01 → 2021-12-30 (113 scenes)' from the list of downloaded scenes; falls back to the nominal window."""
    f = Path(folder) / "downloaded_scenes.csv"
    lo, hi = C.COMPOSITE_WINDOWS[period]
    if f.exists():
        df = pd.read_csv(f)
        if period != "All years":
            df = df[df["year"].astype(str) == period]
        if len(df):
            return f"{df['date'].min()} → {df['date'].max()} ({len(df)} scenes)"
    return f"{lo} → {hi}"


@st.cache_resource(show_spinner=False)
def copernicus_scene(path: str, mtime: float):
    return CI.load(Path(path))


@st.cache_data(ttl=3600, show_spinner=False)
def copernicus_stac(start: str, end: str, max_cloud: float) -> dict:
    return CI.stac_dates(start, end, max_cloud)


# ----------------------------------------------------------------- figures for downloads -----
@st.cache_data(show_spinner=False, max_entries=8)
def ndvi_dist_png(folder: str, mtime: float, style: str = "light") -> bytes:
    return F.to_png(F.ndvi_distribution_figure(load_data(folder, mtime)["ndvis"], style))


@st.cache_data(show_spinner=False, max_entries=16)
def budget_png(folder: str, mtime: float, a: str, b: str, t_mod: float, t_strong: float, style: str = "light") -> bytes:
    return F.to_png(F.budget_figure(budget(folder, mtime, a, b, t_mod, t_strong), a, b, *C.validate_thresholds(t_mod, t_strong)[:2], style))


@st.cache_data(show_spinner=False, max_entries=16)
def hist_png(folder: str, mtime: float, a: str, b: str, t_mod: float, t_strong: float, style: str = "light") -> bytes:
    counts, edges = histogram(folder, mtime, a, b)
    return F.to_png(F.change_histogram_figure(counts, edges, a, b, *C.validate_thresholds(t_mod, t_strong)[:2], style))


@st.cache_data(show_spinner=False, max_entries=8)
def aoi_png(folder: str, mtime: float, a: str, b: str, thr: float, min_ha: float) -> bytes:
    d = load_data(folder, mtime)
    _, gj, _ = patches(folder, mtime, a, b, thr, min_ha)
    rings = []
    for f in gj["features"]:
        for poly in f["geometry"]["coordinates"]:
            rings.append(poly[0])
    rgba = store.load_rgba(folder, "All years" if "All years" in d["ndvis"] else next(iter(d["ndvis"])))
    f_ = max(1, int(np.ceil(max(rgba.shape[:2]) / 700)))
    return F.to_png(F.aoi_map_figure(rgba[::f_, ::f_, :3], d["bounds"], C.AOI_GEOMETRY["coordinates"][0], rings))
