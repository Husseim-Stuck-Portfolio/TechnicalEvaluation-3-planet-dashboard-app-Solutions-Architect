"""How many images went into each composite?

Sources, in order of authority (the first that is available wins):

1. ``composite_counts.json``   - the single record, written by ``precompute`` / the app on first launch.
2. The **download folder** of notebook 2 - one ``ARPS_Para_<date>.tif`` per acquisition that was actually
   fetched from the sandbox collection; this is what the composites were built from.
3. Sentinel Hub **Catalog API** (needs OAuth credentials) - metadata only.

Per period three numbers are kept because they answer different questions:

* ``items``     - GeoTIFFs downloaded (what a per-image median iterates over),
* ``usable``    - those with at least ``MIN_VALID`` of the AOI pixels valid in the ``dataMask`` band,
* ``available`` - catalog entries for the AOI (``all_images_sentinel.csv`` of notebook 2),
* ``dates``     - distinct acquisition days among ``items``.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config as C

YEARS = C.YEARS
MIN_VALID = 0.5          # a file counts as "usable" when >= 50 % of its pixels carry data
_DATE_RE = re.compile(r"(20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?([0-3]\d)")


class CountError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------ #
def _summarise(per_year: dict[str, list[str]], usable: dict[str, int] | None = None,
               available: dict[str, int] | None = None) -> dict:
    """per_year: {'2021': ['2021-06-22T13:00:16Z', ...]} (one entry per image) -> counts dict."""
    out = {}
    for y in YEARS:
        stamps = per_year.get(y, [])
        monthly = Counter(s[5:7] for s in stamps)
        out[y] = {"items": len(stamps), "dates": len({s[:10] for s in stamps}),
                  "usable": None if usable is None else int(usable.get(y, 0)),
                  "available": None if available is None else int(available.get(y, 0)),
                  "monthly": {f"{m:02d}": monthly.get(f"{m:02d}", 0) for m in range(1, 13)}}
    allm = {f"{m:02d}": sum(out[y]["monthly"][f"{m:02d}"] for y in YEARS) for m in range(1, 13)}
    tot = lambda k: None if out[YEARS[0]][k] is None else sum(out[y][k] for y in YEARS)  # noqa: E731
    out["All years"] = {"items": tot("items"), "dates": tot("dates"), "usable": tot("usable"),
                        "available": tot("available"), "monthly": allm}
    return out


def _record(counts: dict, source: str, **extra) -> dict:
    return {"source": source, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "counts": counts, **extra}


def save(record: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2))


def load(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        rec = json.loads(path.read_text())
        return rec if "counts" in rec else None
    except (OSError, json.JSONDecodeError):
        return None


def manual(items: dict[str, int]) -> dict:
    """User typed the numbers (e.g. read off notebook 2). Monthly detail is unknown."""
    counts = {y: {"items": int(items.get(y, 0)), "dates": None, "monthly": None} for y in YEARS}
    counts["All years"] = {"items": sum(counts[y]["items"] for y in YEARS), "dates": None, "monthly": None}
    return _record(counts, "manual entry")


# ------------------------------------------------------------------------------------------ #
def _valid_fraction(path: Path) -> float | None:
    """Share of pixels flagged valid in the last band (``dataMask``) - None if unreadable."""
    try:
        import rasterio
        with rasterio.open(path) as src:
            if src.count < 5:                       # no dataMask: fall back to non-zero first band
                a = src.read(1)
                return float((a != 0).mean())
            return float((src.read(src.count) > 0).mean())
    except Exception:  # noqa: BLE001 - one broken file must not stop the count
        return None


def list_downloads(folder: Path) -> list[tuple[str, Path]]:
    """(``YYYY-MM-DD``, path) for every dated GeoTIFF directly in ``folder`` (composites excluded)."""
    out = []
    for p in sorted(Path(folder).glob("*.tif*")):          # non-recursive: sub-folders hold screenshots / other data
        if p.name.lower().startswith("composite"):
            continue
        m = _DATE_RE.search(p.stem)
        if m:
            out.append((f"{m.group(1)}-{m.group(2)}-{m.group(3)}", p))
    return out


def from_download_folder(folder: Path, coverage: bool = True, min_valid: float = MIN_VALID,
                         catalog_csv: Path | None = None, index_csv: Path | None = None,
                         progress=None) -> dict:
    """Count the per-date GeoTIFFs of notebook 2 (and, optionally, how much of each is valid).

    ``index_csv`` receives one row per file (``file,date,year,valid_pct``) so the app can list them.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise CountError(f"Download folder not found: {folder}")
    files = [(d, p) for d, p in list_downloads(folder) if d[:4] in YEARS]
    if not files:
        raise CountError(f"No dated GeoTIFFs for {', '.join(YEARS)} found in {folder}")
    per_year: dict[str, list[str]] = defaultdict(list)
    usable: Counter = Counter()
    rows = []
    for i, (d, p) in enumerate(files):
        y = d[:4]
        per_year[y].append(f"{d}T00:00:00Z")
        vf = _valid_fraction(p) if coverage else None
        if vf is not None and vf >= min_valid:
            usable[y] += 1
        rows.append((p.name, d, y, None if vf is None else round(100 * vf, 2)))
        if progress:
            progress(i + 1, len(files))
    if index_csv:
        Path(index_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(index_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "date", "year", "valid_pct"])
            w.writerows(rows)
    available = catalog_counts(catalog_csv) if catalog_csv and Path(catalog_csv).exists() else None
    rec = _record(_summarise(per_year, usable if coverage else None, available),
                  f"downloaded scenes ({len(files)} GeoTIFFs)", min_valid=min_valid)
    return rec


def catalog_counts(csv_path: Path) -> dict[str, int]:
    """Catalog entries per year from ``all_images_sentinel.csv`` (columns: id, datetime, date)."""
    out: Counter = Counter()
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            stamp = (r.get("datetime") or r.get("date") or "")[:4]
            if stamp in YEARS:
                out[stamp] += 1
    return dict(out)


# ------------------------------------------------------------------------------------------ #
def sh_token(client_id: str, client_secret: str, timeout: int = 30) -> str:
    r = requests.post(C.SH_TOKEN_URL, timeout=timeout, data={
        "grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret})
    if r.status_code in (400, 401):
        raise CountError("Sentinel Hub rejected the OAuth client id/secret.")
    r.raise_for_status()
    return r.json()["access_token"]


def from_sentinel_hub(client_id: str, client_secret: str, collection: str = C.SH_COLLECTION,
                      max_pages: int = 50, session: requests.Session | None = None) -> dict:
    """Catalog API search per year (paged with ``next``). Metadata only; no imagery is downloaded."""
    s = session or requests.Session()
    token = sh_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    per_year: dict[str, list[str]] = {}
    for y in YEARS:
        stamps: list[str] = []
        body = {"collections": [collection], "intersects": C.AOI_GEOMETRY, "limit": 100,
                "datetime": f"{y}-01-01T00:00:00Z/{y}-12-31T23:59:59Z"}
        for _ in range(max_pages):
            r = s.post(C.SH_CATALOG_URL, json=body, headers=headers, timeout=60)
            if r.status_code == 401:
                raise CountError("Sentinel Hub token rejected (401).")
            r.raise_for_status()
            js = r.json()
            stamps += [f["properties"]["datetime"] for f in js.get("features", []) if "datetime" in f.get("properties", {})]
            nxt = js.get("context", {}).get("next")
            if not nxt:
                break
            body = {**body, "next": nxt}
        per_year[y] = stamps
    return _record(_summarise(per_year), "Sentinel Hub Catalog API", collection=collection)


def resolve(processed_dir: Path, download_dir: Path | None = None, catalog_csv: Path | None = None,
            progress=None) -> dict | None:
    """Best available record without credentials: saved json, else scan the download folder (and save it)."""
    processed_dir = Path(processed_dir)
    rec = load(processed_dir / "composite_counts.json")
    if rec:
        return rec
    if download_dir:
        try:
            rec = from_download_folder(download_dir, catalog_csv=catalog_csv,
                                       index_csv=processed_dir / "downloaded_scenes.csv", progress=progress)
            save(rec, processed_dir / "composite_counts.json")
            return rec
        except CountError:
            return None
    return None
