"""Business logic: turns NDVI composites into decision-ready numbers.

Implements ideas 1, 2, 3 and 10 of the ideas PDF ("change budget", "trajectories",
"disturbance patches", "threshold sensitivity"). Every function is pure (arrays in, tables out) so
it can be unit-tested, used from the notebook and cached by Streamlit.

Interpretation caveat (kept visible in the UI): an NDVI *decrease* is a candidate disturbance, not
confirmed deforestation. Composites are built from different acquisition sets, so part of any
difference can be atmospheric / phenological / radiometric rather than real.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import ndimage

from . import theme as T

PATCH_COLUMNS = ["patch_id", "area_ha", "pixels", "mean_change", "max_decline", "ndvi_2021", "ndvi_2022", "ndvi_2023",
                 "compactness", "lon", "lat", "robustness", "declining_21_22_pct", "recovering_22_23_pct", "bbox"]
EMPTY_COLLECTION = {"type": "FeatureCollection", "features": []}
CATEGORIES = ["Strong decrease", "Moderate decrease", "Little change", "Moderate increase", "Strong increase"]
_STRUCT8 = np.ones((3, 3), dtype=bool)


def area_ha(mask: np.ndarray, area_row: np.ndarray) -> float:
    """Area (ha) of a boolean mask given per-row pixel areas."""
    return float(mask.sum(axis=1, dtype=np.float64) @ area_row)


# ------------------------------------------------------------------------------------------ #
# Idea 1 - change budget
# ------------------------------------------------------------------------------------------ #
def change_budget(a: np.ndarray, b: np.ndarray, area_row: np.ndarray,
                  t_mod: float = 0.10, t_strong: float = 0.20) -> pd.DataFrame:
    """Area per NDVI-change class for ``b - a``. Unobserved pixels are reported separately and are
    excluded from the percentage denominator (never treated as 'no change')."""
    if not 0 < t_mod < t_strong:
        raise ValueError("Need 0 < moderate threshold < strong threshold")
    d = b - a
    valid = np.isfinite(d)
    masks = {
        "Strong decrease": d <= -t_strong,
        "Moderate decrease": (d > -t_strong) & (d <= -t_mod),
        "Little change": (d > -t_mod) & (d < t_mod),
        "Moderate increase": (d >= t_mod) & (d < t_strong),
        "Strong increase": d >= t_strong,
    }
    total = area_ha(valid, area_row)
    rows = []
    for name in CATEGORIES:
        m = masks[name] & valid
        ha = area_ha(m, area_row)
        rows.append({"class": name, "pixels": int(m.sum()), "area_ha": ha,
                     "pct_valid": 100 * ha / total if total else np.nan})
    rows.append({"class": "No data", "pixels": int((~valid).sum()),
                 "area_ha": area_ha(~valid, area_row), "pct_valid": np.nan})
    return pd.DataFrame(rows)


def change_histogram(a: np.ndarray, b: np.ndarray, lim: float = 0.6, bins: int = 120):
    d = (b - a)[np.isfinite(b - a)]
    counts, edges = np.histogram(d, bins=bins, range=(-lim, lim))
    return counts, edges


# ------------------------------------------------------------------------------------------ #
# Idea 2 - trajectories (three annual points -> classification, not a statistical trend)
# ------------------------------------------------------------------------------------------ #
def trajectory(n21: np.ndarray, n22: np.ndarray, n23: np.ndarray, tau: float = 0.10) -> np.ndarray:
    """uint8 class map, see ``theme.TRAJECTORY``. ``tau`` = minimum |dNDVI| that counts as change."""
    d1, d2 = n22 - n21, n23 - n22
    valid = np.isfinite(d1) & np.isfinite(d2)
    s1 = np.where(d1 <= -tau, -1, np.where(d1 >= tau, 1, 0))
    s2 = np.where(d2 <= -tau, -1, np.where(d2 >= tau, 1, 0))
    out = np.zeros(d1.shape, dtype=np.uint8)
    out[valid & (s1 == 0) & (s2 == 0)] = 1
    out[valid & (((s1 == 1) & (s2 >= 0)) | ((s1 == 0) & (s2 == 1)))] = 2
    out[valid & (((s1 == -1) & (s2 <= 0)) | ((s1 == 0) & (s2 == -1)))] = 3
    out[valid & (s1 == -1) & (s2 == 1)] = 4
    out[valid & (s1 == 1) & (s2 == -1)] = 5
    return out


def trajectory_table(traj: np.ndarray, area_row: np.ndarray) -> pd.DataFrame:
    valid_ha = area_ha(traj > 0, area_row)
    rows = []
    for k, (label, color) in T.TRAJECTORY.items():
        ha = area_ha(traj == k, area_row)
        rows.append({"class": label, "area_ha": ha,
                     "pct_valid": (100 * ha / valid_ha) if (k and valid_ha) else np.nan, "color": color})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------ #
# Idea 3 - disturbance patches
# ------------------------------------------------------------------------------------------ #
def decline_mask(change: np.ndarray, thr: float, clean: bool = True) -> np.ndarray:
    m = np.isfinite(change) & (change <= -thr)
    if clean:  # open then close with 3x3 (same cleaning as notebook 3): drops speckle, fills pin-holes
        m = ndimage.binary_opening(m, structure=_STRUCT8)
        m = ndimage.binary_closing(m, structure=_STRUCT8)
    return m


def _perimeter_m(sub: np.ndarray, dx_m: float, dy_m: float) -> float:
    p = np.pad(sub, 1)
    c = p[1:-1, 1:-1]
    tb = (c & ~p[:-2, 1:-1]).sum() + (c & ~p[2:, 1:-1]).sum()   # edges facing north/south: length dx
    lr = (c & ~p[1:-1, :-2]).sum() + (c & ~p[1:-1, 2:]).sum()   # edges facing east/west:  length dy
    return float(tb * dx_m + lr * dy_m)


def detect_patches(ndvis: dict[str, np.ndarray], from_year: str, to_year: str, thr: float,
                   min_ha: float, area_row: np.ndarray, bounds: tuple, max_patches: int = 500,
                   robustness_grid=(0.10, 0.15, 0.20, 0.25, 0.30)):
    """Connected NDVI-decline patches between two annual composites.

    Returns (DataFrame ranked by area, GeoJSON FeatureCollection, summary dict). Per patch:
    area, mean/max decline, NDVI per year, share of pixels already declining in 2021->2022 and
    share *recovering* in 2022->2023 (high recovery = likely temporary), compactness and a
    robustness score = fraction of tested thresholds at which the patch's median change still
    qualifies (a statement about robustness to our settings, NOT a probability of deforestation).
    """
    from rasterio import features
    from rasterio.transform import from_bounds

    a, b = ndvis[from_year], ndvis[to_year]
    change = b - a
    h, w = change.shape
    west, south, east, north = bounds
    transform = from_bounds(west, south, east, north, w, h)
    ha_px = float(np.mean(area_row))
    min_px = max(1, int(round(min_ha / ha_px)))
    lat_c = (south + north) / 2
    dx_m = (east - west) / w * 111412.84 * np.cos(np.radians(lat_c))
    dy_m = (north - south) / h * 111132.92

    mask = decline_mask(change, thr)
    labels, n = ndimage.label(mask, structure=_STRUCT8)
    summary = {"total_candidates": int(n), "min_px": min_px, "declined_ha": area_ha(mask, area_row)}
    summary.update(kept=0, kept_ha=0.0)
    if n == 0:
        return pd.DataFrame(columns=PATCH_COLUMNS), {"type": "FeatureCollection", "features": []}, summary
    sizes = np.bincount(labels.ravel())[1:]
    ids = np.flatnonzero(sizes >= min_px) + 1
    if len(ids) == 0:          # nothing reaches the minimum size: an empty result, not an error
        return pd.DataFrame(columns=PATCH_COLUMNS), {"type": "FeatureCollection", "features": []}, summary
    ids = ids[np.argsort(-sizes[ids - 1])][:max_patches]
    summary["kept"] = int(len(ids))
    summary["kept_ha"] = float(sum(sizes[i - 1] for i in ids) * ha_px)

    slices = ndimage.find_objects(labels)
    d1 = ndvis["2022"] - ndvis["2021"] if {"2021", "2022"} <= ndvis.keys() else None
    d2 = ndvis["2023"] - ndvis["2022"] if {"2022", "2023"} <= ndvis.keys() else None
    tau = thr / 2
    rows = []
    for rank, lab in enumerate(ids, start=1):
        sl = slices[lab - 1]
        sub = labels[sl] == lab
        r_idx, c_idx = np.nonzero(sub)
        rr, cc = r_idx + sl[0].start, c_idx + sl[1].start
        ch = change[sl][sub]
        ha = float(area_row[rr].sum())
        perim = _perimeter_m(sub, dx_m, dy_m)
        med = float(np.median(ch))
        row = {
            "patch_id": rank, "area_ha": ha, "pixels": int(sub.sum()),
            "mean_change": float(ch.mean()), "max_decline": float(ch.min()),
            f"ndvi_{from_year}": float(a[sl][sub].mean()), f"ndvi_{to_year}": float(b[sl][sub].mean()),
            "compactness": float(4 * np.pi * ha * 1e4 / perim ** 2) if perim else np.nan,
            "lon": float(west + (cc.mean() + 0.5) * (east - west) / w),
            "lat": float(north - (rr.mean() + 0.5) * (north - south) / h),
            "robustness": float(np.mean([med <= -t for t in robustness_grid])),
        }
        for y in ("2021", "2022", "2023"):
            if y in ndvis:
                row[f"ndvi_{y}"] = float(np.nanmean(ndvis[y][sl][sub]))
        if d1 is not None:
            row["declining_21_22_pct"] = float(100 * np.mean(d1[sl][sub] <= -tau))
        if d2 is not None:
            row["recovering_22_23_pct"] = float(100 * np.mean(d2[sl][sub] >= tau))
        row["bbox"] = [float(west + sl[1].start * (east - west) / w), float(north - sl[0].stop * (north - south) / h),
                       float(west + sl[1].stop * (east - west) / w), float(north - sl[0].start * (north - south) / h)]
        rows.append(row)
    df = pd.DataFrame(rows)

    # polygons (only kept patches) -> GeoJSON, id = rank
    lut = np.zeros(n + 1, dtype=np.int32)
    lut[ids] = np.arange(1, len(ids) + 1, dtype=np.int32)
    keep = lut[labels]
    by_id: dict[int, list] = {}
    for geom, val in features.shapes(keep, mask=keep > 0, transform=transform, connectivity=8):
        by_id.setdefault(int(val), []).append(geom["coordinates"])
    props = df.set_index("patch_id")
    feats = []
    for pid, polys in by_id.items():
        if pid not in props.index:
            continue
        p = props.loc[pid]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": _round(polys)},
            "properties": {"patch_id": int(pid), "area_ha": round(float(p.area_ha), 2),
                           "mean_change": round(float(p.mean_change), 3),
                           "robustness": round(float(p.robustness), 2)},
        })
    return df, {"type": "FeatureCollection", "features": feats}, summary


def _round(x, nd: int = 6):
    if isinstance(x, (list, tuple)):
        return [_round(i, nd) for i in x]
    return round(float(x), nd)


# ------------------------------------------------------------------------------------------ #
# Idea 10 - sensitivity of the headline number to analyst choices
# ------------------------------------------------------------------------------------------ #
def sensitivity(a: np.ndarray, b: np.ndarray, area_row: np.ndarray, thresholds, min_has) -> pd.DataFrame:
    change = b - a
    ha_px = float(np.mean(area_row))
    rows = []
    for t in thresholds:
        lab, n = ndimage.label(decline_mask(change, t), structure=_STRUCT8)
        sizes = np.bincount(lab.ravel())[1:] if n else np.array([], dtype=int)
        for mh in min_has:
            keep = sizes >= max(1, int(round(mh / ha_px)))
            rows.append({"threshold": t, "min_patch_ha": mh, "patches": int(keep.sum()),
                         "area_ha": float(sizes[keep].sum() * ha_px)})
    return pd.DataFrame(rows)
