"""Heavy lifting done once, outside Streamlit (the app only loads analysis-ready files).

    python -m para_explorer.precompute            # defaults: ../composites, ../planet_downloads, ../all_images_sentinel.csv
        [--composites DIR] [--downloads DIR] [--catalog CSV] [--out data/processed]
        [--sh-client-id ... --sh-client-secret ...]      # or env SH_CLIENT_ID / SH_CLIENT_SECRET

Reads the 4-band composites of notebook 3 and writes to ``--out``:
    ndvi_<period>.tif        single-band float32 NDVI (full resolution, georeferenced)
    rgb_<period>.png         RGBA true-colour preview (<= 1200 px, common contrast stretch)
    meta.json                bounds / shape / CRS / stretch limits / flags
    composite_counts.json    images used per composite (Sentinel Hub catalog > download folder > kept)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from . import composites as K
from . import config as C
from . import counts as N


def run(raw_dir: Path, out_dir: Path, download_dir: Path | None = None,
        sh_id: str | None = None, sh_secret: str | None = None,
        catalog_csv: Path | None = None, coverage: bool = True, max_px: int = 1200, log=print) -> dict:
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = K.raw_composite_path(raw_dir, "All years")
    present = {n: K.raw_composite_path(raw_dir, n) for n in C.COMPOSITES if K.raw_composite_path(raw_dir, n).exists()}
    if not present:
        raise FileNotFoundError(f"No composite_*.tif files in {raw_dir}")
    ref = ref if ref.exists() else next(iter(present.values()))
    lims = K.rgb_limits(K.read_bands(ref, [1, 2, 3], max_px))
    info = K.raster_info(ref)

    for name, path in present.items():
        ndvi = K.read_ndvi(path)
        with rasterio.open(path) as src:
            prof = dict(driver="GTiff", dtype="float32", count=1, width=src.width, height=src.height,
                        crs=src.crs, transform=src.transform, nodata=np.nan, compress="deflate",
                        predictor=3, tiled=True, blockxsize=256, blockysize=256)
        with rasterio.open(out_dir / f"ndvi_{C.slug(name)}.tif", "w", **prof) as dst:
            dst.write(ndvi, 1)
        rgba = K.to_rgba_uint8(K.read_bands(path, [1, 2, 3], max_px), lims)
        Image.fromarray(rgba, "RGBA").save(out_dir / f"rgb_{C.slug(name)}.png", optimize=True)
        log(f"[ok] {name}: NDVI {ndvi.shape}, valid {np.isfinite(ndvi).mean():.2%}")

    meta = {"bounds": info["bounds"], "width": info["width"], "height": info["height"], "crs": info["crs"],
            "periods": list(present), "rgb_limits": lims, "rgb_max_px": max_px}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    rec = None
    sh_id, sh_secret = sh_id or os.getenv("SH_CLIENT_ID"), sh_secret or os.getenv("SH_CLIENT_SECRET")
    try:
        if sh_id and sh_secret:
            rec = N.from_sentinel_hub(sh_id, sh_secret)
        elif download_dir:
            rec = N.from_download_folder(download_dir, coverage=coverage, catalog_csv=catalog_csv,
                                         index_csv=out_dir / "downloaded_scenes.csv")
    except Exception as e:  # keep going: counts are optional at this stage
        log(f"[warn] could not count images: {e}")
    if rec:
        N.save(rec, out_dir / "composite_counts.json")
        log("[ok] image counts (downloaded/usable/available): " + ", ".join(
            f"{k}={v['items']}/{v.get('usable')}/{v.get('available')}" for k, v in rec["counts"].items()))
    elif not (out_dir / "composite_counts.json").exists():
        log("[info] no image counts yet - pass --downloads or Sentinel Hub credentials (or enter them in the app)")
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--composites", type=Path, default=C.RAW_COMPOSITES_DIR, help="folder with composite_2021.tif ... composite_All_years.tif")
    ap.add_argument("--out", type=Path, default=C.PROCESSED_DIR)
    ap.add_argument("--downloads", type=Path, default=C.DOWNLOADS_DIR, help="folder with the per-date GeoTIFFs of notebook 2")
    ap.add_argument("--catalog", type=Path, default=C.CATALOG_CSV, help="all_images_sentinel.csv of notebook 2")
    ap.add_argument("--no-coverage", action="store_true", help="skip reading every download for its valid-pixel share")
    ap.add_argument("--sh-client-id")
    ap.add_argument("--sh-client-secret")
    a = ap.parse_args()
    run(a.composites, a.out, a.downloads if a.downloads.is_dir() else None, a.sh_client_id, a.sh_client_secret,
        catalog_csv=a.catalog, coverage=not a.no_coverage)


if __name__ == "__main__":
    main()
