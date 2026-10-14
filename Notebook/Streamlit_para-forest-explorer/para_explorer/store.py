"""Loads the analysis-ready files written by ``precompute`` (what Streamlit actually reads)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from . import config as C


def status(folder: Path) -> dict:
    folder = Path(folder)
    meta = folder / "meta.json"
    if not meta.exists():
        return {"ok": False, "reason": f"No meta.json in {folder}"}
    m = json.loads(meta.read_text())
    missing = [p for p in m["periods"] if not (folder / f"ndvi_{C.slug(p)}.tif").exists()]
    if missing:
        return {"ok": False, "reason": f"Missing NDVI files for {missing}"}
    return {"ok": True, "meta": m}


def load_ndvis(folder: Path) -> dict[str, np.ndarray]:
    out = {}
    for p in json.loads((Path(folder) / "meta.json").read_text())["periods"]:
        with rasterio.open(Path(folder) / f"ndvi_{C.slug(p)}.tif") as src:
            out[p] = src.read(1).astype("float32")
    return out


def load_rgba(folder: Path, period: str) -> np.ndarray:
    return np.array(Image.open(Path(folder) / f"rgb_{C.slug(period)}.png").convert("RGBA"))
