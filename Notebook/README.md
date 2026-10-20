# Pará Forest Change Explorer: notebooks and app

Where did vegetation get less green between 2021 and 2023 in a 568 km² area of Pará, Brazil, how large is that area, and how much can the result be trusted?

The project has two parts that share the same data:

| Part | What it is | Start here |
|---|---|---|
| **Notebooks** (3) | The analysis, step by step: find imagery → prepare annual composites → calculate NDVI change and decline patches | `1_planet_imagery_discovery_api.ipynb` |
| **Streamlit app** | An interactive explorer for the results: globe map, image counts, NDVI change, decline patches, Planet API search, Planet vs Copernicus comparison, downloads and a PDF report | `Streamlit_para-forest-explorer/app.py` |

> **Important:** NDVI change shows areas to investigate. It is **not** proof of deforestation. Seasonality, clouds, fire, drought or harvest can also lower NDVI.

---

## 1. Quick start (the app, about 2 minutes)

You need Python 3.10 or newer. No account or key is needed to open the app: the analysis-ready data is included.

```bash
cd Streamlit_para-forest-explorer
python3 -m venv .venv
source .venv/bin/activate                 # Windows PowerShell:  .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The app opens in your browser. If it does not, open `http://localhost:8501`.

To run the notebooks as well, install the full list instead (from this folder) and start Jupyter here, because the notebooks use relative paths:

```bash
python -m pip install -r requirements.txt
jupyter lab
```

## 2. What is in this folder

```text
Notebook/
├── README.md                                  this file
├── requirements.txt                           libraries for the notebooks and the app
├── 1_planet_imagery_discovery_api.ipynb       Part 1: find and inspect Planet imagery
├── 2_planet_data_preparatioin_sentinelhub.ipynb   Part 2: download bands, build annual composites
├── 3_planet_ndvi_analysis_sentinelhub.ipynb   Part 3: NDVI, change classes, decline patches
├── all_images_values.csv                      output of notebook 1 (76 Planet scenes)
├── all_images_sentinel.csv                    output of notebook 2 (677 catalog items, 2021-2023)
├── sandbox_para_brazil_polygons.geojson       area-of-interest polygons
├── composites/                                annual composites (input of notebook 3) and its CSV outputs
└── Streamlit_para-forest-explorer/
    ├── app.py                                 start the app with: streamlit run app.py
    ├── requirements.txt                       libraries for the app only
    ├── README.md                              app details
    ├── para_explorer/                         app code (analysis, map, API clients, views)
    ├── data/                                  area of interest + analysis-ready files (data/processed)
    ├── scripts/                               static figures
    ├── tests/                                 automated tests
    └── version_1_app copy.py                  early prototype, kept for reference (not used)
```

### Satellite images

The original dataset has about 300 daily satellite images (317 GeoTIFFs, more than 12 GB), so they are **not** included. The **annual composites** are included instead: one image per period, covering **2021, 2022, 2023 and all years combined** (`composites/`). Everything in the notebooks from Part 3 on, and everything in the app, works from them. The original images can be provided separately on request.

## 3. The notebooks

Run them in order. Each one ends with a pointer to the next. Run every notebook top to bottom after restarting its kernel.

| # | Notebook | What it does | Needs | Writes |
|---|---|---|---|---|
| 1 | Imagery discovery | Searches the Planet Data API for the 76 requested scenes inside the area of interest, shows their metadata and previews | Planet API key (typed at run time) | `all_images_values.csv` |
| 2 | Data preparation | Searches the Planet sandbox collection on Sentinel Hub, downloads the red/green/blue/NIR bands and a valid-pixel mask for every 7th date, then builds the annual median composites | Planet **OAuth client** (ID + secret, typed at run time) | `all_images_sentinel.csv`, `planet_downloads/*.tif`, `composites/composite_*.tif` |
| 3 | NDVI analysis | Loads the composites, calculates NDVI, classifies change (strong/moderate decrease and increase), measures area, finds connected decline patches | Nothing: works offline on `composites/` | `composites/ndvi_statistics.csv`, `change_classes.csv`, `decline_patches.csv` and figures |

Why two different logins? The 2021-2023 sandbox data (`PS_ARD_SR_DAILY`, analysis-ready PlanetScope surface reflectance) is hosted on **Sentinel Hub**, not on `api.planet.com`. A Planet API key gets a 404 there, so notebook 2 uses an OAuth client (Planet account → *OAuth Clients*).

**Without any account**, you can still run **notebook 3** completely and open the app. Notebooks 1 and 2 need credentials. Notebook 2's downloads also use Processing Units from the account, and the composite step needs the downloaded files in `planet_downloads/` (not included).

Credentials are never stored in the notebooks: they are typed into hidden `getpass` prompts.

### Method in short

- **NDVI** = (NIR − Red) / (NIR + Red), from band 3 (red) and band 4 (NIR) of each composite.
- **Change** = NDVI 2023 − NDVI 2021, only where both years have data.
- **Classes:** moderate change ≥ 0.10, strong change ≥ 0.20.
- **Patches:** the strong-decline mask is cleaned (opening, then closing, 3×3), connected pixels are labelled, and patches of at least 100 pixels (≈ 1 ha) are kept.
- **Composites:** per-pixel median over the dates of each period, so clouds and shadows on single dates are ignored.

### Results of the saved run

| Class (NDVI change 2021 → 2023) | Share of valid pixels | Area |
|---|---|---|
| Strong decrease (≤ −0.20) | 0.77 % | 437 ha |
| Moderate decrease (−0.20 to −0.10) | 4.58 % | 2,599 ha |
| Little change | 90.45 % | 51,341 ha |
| Moderate increase (0.10 to 0.20) | 3.87 % | 2,198 ha |
| Strong increase (≥ 0.20) | 0.33 % | 186 ha |

The strong decline forms 311 patches; 55 are at least 1 ha, the largest about 24 ha. Mean NDVI is almost unchanged (0.810 → 0.807), so the change is concentrated in a few places rather than spread evenly.

## 4. The app

Start it from `Streamlit_para-forest-explorer/` (see section 1).

**Page layout**

- **Top:** short introduction for readers new to satellite data (collapsed; click to open), key numbers, and the 3-D globe with the composite, NDVI, change or trajectory layers and the decline patches.
- **Sidebar**, in five groups: *Map layer* (period, layer, patches) · *Change analysis* (years, thresholds) · *Decline patches* (size and robustness filters) · *Map display* (basemap, opacity, globe intro) · *Planet imagery search* (API key, area, cloud and date filters). Each group says what it changes.
- **Tabs:** Composites & image counts · NDVI change · Decline patches · Planet imagery (API) · Copernicus context · Method & limits.
- **Bottom:** downloads (PNG charts, CSV tables, PDF report) and the **Planet vs Copernicus** side-by-side comparison.

**What works without credentials:** the globe, composites and image counts, NDVI change, decline patches, Method & limits, all downloads, the Copernicus scene availability (public catalogue) and the Planet vs Copernicus comparison for **2021 at the default cloud limit** (a Copernicus image is stored with the app).

**What needs credentials (optional):**

| Feature | Credential | How to provide it |
|---|---|---|
| Planet imagery tab (scene counts, thumbnails, footprints) | Planet API key | Sidebar field, or `PLANET_API_KEY` |
| Planet vs Copernicus for other periods or cloud limits | Free Copernicus Data Space OAuth client | The expander in that section, or `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET` |

Without a Planet key you can upload `all_images_values.csv` (from notebook 1) in the sidebar to see the scene statistics.

To get a Copernicus client: create a free account at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/), open the dashboard, and under **User settings → OAuth clients** create a client. Keep the `client_secret` private.

For a deployment, set the same names as environment variables, or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (that file is git-ignored). **Never put real keys in the code or in the submitted ZIP.**

**Data and folders.** On first launch the app reads `Streamlit_para-forest-explorer/data/processed/` (included). If that folder is missing, it rebuilds it from `../composites/` in about a minute. Only real data is used; there is no synthetic fallback. Folders can be changed with `PARA_NOTEBOOK_DIR`, `PARA_COMPOSITES_DIR`, `PARA_DOWNLOADS_DIR` and `PARA_CATALOG_CSV`.

**Tests:** from `Streamlit_para-forest-explorer/`, run `python -m pytest tests`.

## 5. Notes and limitations

- **Not deforestation proof.** The annual composites mix different dates and seasons, so rainfall and phenology can change NDVI. Three annual points give a classification, not a trend.
- **Thresholds are choices.** 0.10, 0.20 and the 1 ha minimum patch size are analyst decisions; the app lets you change the thresholds between 0.10 and 0.20 and shows a sensitivity chart.
- **Dense forest saturates NDVI** (around 0.8-0.9), so it detects clearing better than degradation inside closed forest.
- **Image counts** in the app are the number of dated files per period (downloaded, with at least 50 % valid pixels, and in the catalog). They are not counts of clear observations.
- **Composite step.** The code that first produced the composites was not saved. The composite cell in notebook 2 is a reconstruction (a per-pixel median, which a comparison with the downloaded files supports). It never overwrites existing composites and has only been tested on small synthetic data.
- **Live API calls** (Planet, Sentinel Hub, Copernicus) follow the public documentation and are covered by automated tests with simulated responses.
- **Licence.** The sandbox imagery is CC-BY-NC (non-commercial) and covers 2021-01-01 to 2023-12-29.
- **Future scope** (same-season comparison, monthly time series, rainfall and fire data, PRODES/DETER/MapBiomas comparison, alerts and more) is listed at the end of notebook 3.
