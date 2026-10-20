# Pará Forest Change Explorer: Streamlit app

An interactive explorer for NDVI change between annual PlanetScope composites (2021, 2022, 2023, all years) over a 568 km² forest area in Pará, Brazil. It shows where vegetation vigour dropped, how large and how persistent the change is, how many images stand behind each composite, and how much to trust it.

The full project guide (notebooks, data, accounts, results) is in the parent folder's `README.md`.

## Run it

Python 3.10 or newer. No account or key is needed: the analysis-ready data is in `data/processed/`.

```bash
python3 -m venv .venv
source .venv/bin/activate                 # Windows PowerShell:  .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py                      # http://localhost:8501
```

Works with Streamlit 1.40 and newer. Tests: `python -m pytest tests`.

## What you see

| Area | What it does | Code |
|---|---|---|
| **Globe map** | 3-D globe (EOX Sentinel-2 cloudless or Esri basemap) with the area of interest, true colour / NDVI / change / trajectory layers, clickable decline patches and Planet scene footprints | `globe.py`, `views/overview.py` |
| **Composites & image counts** | Images behind each composite (2021, 2022, 2023, all years) and per month; the four composites side by side | `counts.py`, `views/composites_tab.py` |
| **NDVI change** | Change budget (ha, %), histogram, change map, 3-year trajectory classes, threshold sensitivity | `analysis.py`, `views/change_tab.py` |
| **Decline patches** | Connected patches ranked by area with a robustness score; selecting a row flies the globe to the patch | `analysis.detect_patches`, `views/patches_tab.py` |
| **Planet imagery (API)** | Your Planet API key, cloud and date filters, scenes per month and year, thumbnail grid streamed through the API (nothing is saved) | `planet.py`, `views/planet_tab.py` |
| **Copernicus context** | Sentinel-2 L2A scene availability for the area from the public Copernicus STAC catalogue | `cdse.py`, `views/copernicus_tab.py` |
| **Planet vs Copernicus** | Same area, same pixel grid, side by side with correlation, bias and RMSE | `views/compare.py`, `copernicus_imagery.py` |
| **Downloads** | PNG charts, CSV tables, a ZIP of composites and a PDF report | `views/downloads.py`, `report.py` |

**Sidebar**, in five groups, each with a one-line description: *Map layer* · *Change analysis* · *Decline patches* · *Map display* · *Planet imagery search*. Thresholds update the map, key numbers, charts and the patch table; a patch-table row moves the globe; cloud and date filters update the Planet charts, previews and footprints. The introduction for readers new to satellite data is collapsed by default.

## Credentials (optional)

| Feature | Credential | Where |
|---|---|---|
| Planet imagery tab | `PLANET_API_KEY` | Sidebar field, environment variable, or `.streamlit/secrets.toml` |
| Planet vs Copernicus for other periods or cloud limits | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` (free OAuth client: Copernicus Data Space dashboard → User settings → OAuth clients) | Expander in that section, environment variable, or `.streamlit/secrets.toml` |

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (git-ignored) to store them locally. Typed values stay in the browser session only and are never displayed, saved or logged. **Never commit real keys or include them in a ZIP.** Without any key, the 2021 comparison at the default cloud limit still works, because a Copernicus image is stored with the app.

## Data

- **Input:** `composite_2021.tif … composite_All_years.tif` from notebook 3 (bands blue, green, red, NIR; float32; EPSG:4326; 2400 × 2400 ≈ 10 m). Source: Planet sandbox collection `PS_ARD_SR_DAILY` via Sentinel Hub (CC-BY-NC, 2021-01-01 to 2023-12-29).
- **Prepared files:** `data/processed/` (NDVI GeoTIFFs, RGB previews, image counts). If it is missing, the first launch rebuilds it from `../composites/` in about a minute, or run `python -m para_explorer.precompute [--composites DIR] [--downloads DIR] [--catalog CSV]`.
- **Real data only.** There is no synthetic fallback. Folders can be changed with `PARA_NOTEBOOK_DIR`, `PARA_COMPOSITES_DIR`, `PARA_DOWNLOADS_DIR`, `PARA_CATALOG_CSV`.
- **Image counts** per period are the dated files downloaded, those with at least 50 % valid pixels, and the items in the catalog. They are not counts of clear observations.
- Areas use the true length of a degree at each raster row. NDVI is a ratio, so the reflectance scale does not matter.
- `python scripts/visualize_composites.py` writes the same analyses as static PNG figures.

## Accuracy notes

An NDVI decrease is a candidate for investigation, not confirmed deforestation. The composites use different sets of dates, so atmospheric and seasonal differences leak into the change. Three annual points give a trajectory classification, not a trend. The robustness score shows how stable a patch is across threshold choices; it is not a probability. Live Planet, Sentinel Hub and Copernicus calls are covered by automated tests with simulated responses.

## Design choices

- **Precompute, then load:** heavy raster work runs once; the app reads analysis-ready files, caches them, and sends overlays of at most 1200 px to the browser.
- **Server-side counts:** the Planet Stats API gives exact counts for the charts instead of paging through thousands of scenes; quick-search results are capped and flagged when truncated.
- **Clear errors:** HTTP 401, 403, 429 and timeouts become readable messages with retries; an API failure never crashes the app.
- **Imagery stays behind the API:** thumbnails are fetched per page with your key, kept in memory, and never written to disk.
- **One logic layer** (`para_explorer/`) shared by the app, the scripts and the tests.
