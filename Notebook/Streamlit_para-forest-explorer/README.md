# Pará Forest Change Explorer

A Streamlit web app that turns annual **PlanetScope** composites (2021, 2022, 2023, all years) over a
568 km² forest area in **Pará, Brazil** into decision-ready answers: *where did vegetation vigour drop,
how large and how persistent is it, how many images stand behind each composite, and how much can I trust it?*
It also streams **Planet Data API** scene previews (cloud/date filters, monthly/yearly availability) and adds
**Copernicus Data Space Ecosystem** context. The area of interest is the GeoJSON exported from the CDSE browser.

## Objective (user story)
A forest-monitoring analyst wants candidate disturbance areas, with size, persistence and a robustness indication,
before sending a field team or cross-checking PRODES/DETER. Planet's frequent imagery makes the temporal analysis
possible; the app makes the evidence transparent (image counts, sensitivity to thresholds, explicit caveats).

## Core components
| Component | What it does | Code |
|---|---|---|
| **Globe map** | Rotating/interactive 3-D globe (MapLibre; EOX Sentinel-2 cloudless or Esri basemap) with AOI, true colour / NDVI / change / trajectory overlays, decline patches (click for stats), Planet scene footprints | `globe.py`, `views/overview.py` |
| **Composites & image counts** | Images used per composite (2021, 2022, 2023, All years) and per month; four composites side by side | `counts.py`, `views/composites_tab.py` |
| **NDVI change** | Change budget (ha, %), ΔNDVI histogram, change map, 3-year trajectory classes, threshold sensitivity | `analysis.py`, `views/change_tab.py` |
| **Decline patches** | Connected patches ranked by area with a robustness score; selecting a row flies the globe to the patch and opens the inspector | `analysis.detect_patches`, `views/patches_tab.py` |
| **Planet imagery (API)** | Prompts for the user's API key, cloud-cover and date filters, bar charts of scenes per month / per year / per calendar month, thumbnail grid streamed through the API (no download) | `planet.py`, `views/planet_tab.py` |
| **Copernicus context** | Sentinel-2 L2A scene availability for the AOI from the public CDSE STAC API | `cdse.py`, `views/copernicus_tab.py` |
| **Precompute** | One-off CLI: raw 4-band composites → NDVI GeoTIFFs, RGB previews, image counts | `precompute.py` |
| **Static figures** | The same analyses as PNG figures for the notebook / report | `scripts/visualize_composites.py` |

Interactivity: sidebar thresholds update map, KPIs, charts and patch table; a patch-table row updates globe and inspector;
a year-bar click (or focus year) filters Planet previews and footprints; cloud/date filters update charts, previews and footprints.

## Data used and assumptions
* **Composites**: `composite_2021.tif … composite_All_years.tif` from notebook 3 (4 bands B,G,R,NIR; float32; EPSG:4326; 2400×2400 ≈ 10 m).
  Source: Planet sandbox collection `PS_ARD_SR_DAILY` via Sentinel Hub (CC-BY-NC, 2021-01-01 → 2023-12-29).
* **Image counts** (per year and for all years): *downloaded* = the dated `ARPS_Para_<date>.tif` files in `planet_downloads`
  (notebook 2); *≥50 % valid* = those whose `dataMask` band is valid over at least half the AOI; *in catalog* = items listed in
  `all_images_sentinel.csv`. They can also come from the Sentinel Hub Catalog API or be typed in the app. None is a count of clear observations. The notebooks provided do not contain the cell that built the composites,
  so check the definition against how you built them.
* **Planet Data API**: key via HTTP Basic; `cloud_percent` is the cloud field (as in notebook 1). Counts via the Stats API, previews via quick-search + thumbnail links.
* Areas use WGS-84 degree lengths per raster row; NDVI is a ratio so the DN scale is irrelevant.
* **Only real data is used.** The app reads the notebooks' own folders (`../composites`, `../planet_downloads`, `../all_images_sentinel.csv`); there is no synthetic fallback. Override with `PARA_NOTEBOOK_DIR`, `PARA_COMPOSITES_DIR`, `PARA_DOWNLOADS_DIR`, `PARA_CATALOG_CSV`.

### Accuracy notes
NDVI decrease ≠ deforestation (candidate only). Composites use different image sets, so atmospheric/phenological differences leak into change.
Three annual points give a trajectory *classification*, not a trend. The robustness score measures robustness to our threshold choices, not a probability.
The live Planet / CDSE / Sentinel Hub calls follow the public API documentation and are unit-tested with mocks; they were not run against live accounts when this was built.

## Local deployment
```bash
python -m venv .venv && source .venv/bin/activate        # Python 3.10+; Streamlit 1.40+ (older and newer both supported)
pip install -r requirements.txt

# 1. app (the first launch builds data/processed from ../composites and counts ../planet_downloads, ≈1 min)
streamlit run app.py          # http://localhost:8501

# optional: build the analysis-ready files yourself / with other folders
python -m para_explorer.precompute [--composites DIR] [--downloads DIR] [--catalog CSV]
```
In the sidebar paste your **Planet API key** (kept in the session only). No key: upload `all_images_values.csv` from notebook 1 for statistics.

Static figures** | The same analyses as PNG figures for the notebook / report | `scripts/visualize_composites.py` |

Interactivity: sidebar thresholds update map, KPIs, charts and patch table; a patch-table row updates globe and inspector;
a year-bar click (or focus year) filters Planet previews and footprints; cloud/date filters update charts, previews and footprints.

## Data used and assumptions
* **Composites**: `composite_2021.tif … composite_All_years.tif` from notebook 3 (4 bands B,G,R,NIR; float32; EPSG:4326; 2400×2400 ≈ 10 m).
  Source: Planet sandbox collection `PS_ARD_SR_DAILY` via Sentinel Hub (CC-BY-NC, 2021-01-01 → 2023-12-29).
* **Image counts** (per year and for all years): *downloaded* = the dated `ARPS_Para_<date>.tif` files in `planet_downloads`
  (notebook 2); *≥50 % valid* = those whose `dataMask` band is valid over at least half the AOI; *in catalog* = items listed in
  `all_images_sentinel.csv`. They can also come from the Sentinel Hub Catalog API or be typed in the app. None is a count of clear observations. The notebooks provided do not contain the cell that built the composites,
  so check the definition against how you built them.
* **Planet Data API**: key via HTTP Basic; `cloud_percent` is the cloud field (as in notebook 1). Counts via the Stats API, previews via quick-search + thumbnail links.
* Areas use WGS-84 degree lengths per raster row; NDVI is a ratio so the DN scale is irrelevant.
* **Only real data is used.** The app reads the notebooks' own folders (`../composites`, `../planet_downloads`, `../all_images_sentinel.csv`); there is no synthetic fallback. Override with `PARA_NOTEBOOK_DIR`, `PARA_COMPOSITES_DIR`, `PARA_DOWNLOADS_DIR`, `PARA_CATALOG_CSV`.

### Accuracy notes
NDVI decrease ≠ deforestation (candidate only). Composites use different image sets, so atmospheric/phenological differences leak into change.
Three annual points give a trajectory *classification*, not a trend. The robustness score measures robustness to our threshold choices, not a probability.
The live Planet / CDSE / Sentinel Hub calls follow the public API documentation and are unit-tested with mocks; they were not run against live accounts when this was built.

## Local deployment
```bash
python -m venv .venv && source .venv/bin/activate        # Python 3.10+; Streamlit 1.40+ (older and newer both supported)
pip install -r requirements.txt

# 1. real data (once): folder with composite_*.tif from notebook 3
python -m para_explorer.precompute --composites /path/to/composites \
       --downloads /path/to/planet_downloads            # counts images per year from the dated GeoTIFFs
#   or: --sh-client-id … --sh-client-secret …            # counts via Sentinel Hub Catalog API (env SH_CLIENT_ID / SH_CLIENT_SECRET also work)

# 2. app
streamlit run app.py          # http://localhost:8501
```
In the sidebar paste your **Planet API key** (kept in the session only). No key: upload `all_images_values.csv` from notebook 1 for statistics.
Without step 1 the app shows the synthetic demo (`python tools/make_demo_data.py` rebuilds it, ~20 s).

Static figures: `python scripts/visualize_composites.py ` (defaults to the notebooks' folders).
Tests: `pytest tests`.

## Design choices worth defending
* **Precompute → load**: heavy raster work runs once; the app reads analysis-ready files, caches arrays as resources and results by parameters, and sends ≤1200 px overlays to the browser.
* **Stats API for charts**: exact server-side counts instead of paging through tens of thousands of scenes; quick-search is capped (default 1,000 scenes) and flagged when truncated.
* **Errors**: 401/403/429/timeouts become actionable messages, with retries and back-off; an API failure never crashes the app.
* **Imagery stays behind the API**: thumbnails are fetched per page with the user's key, held in memory, never written to disk or offered for download.
* **One logic layer** (`para_explorer/`) shared by the notebook script, the app and the tests.
* Next steps: PRODES/DETER/MapBiomas overlay (idea 9), per-pixel clear-observation counts, seasonal anomalies with more dates.
