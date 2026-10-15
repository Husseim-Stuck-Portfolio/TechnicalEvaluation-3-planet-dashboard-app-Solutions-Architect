"""Rebuild the three notebooks in a minimal form (v2).

Reads the current notebooks from SRC (a copy made before this script runs), writes cleaned notebooks to ROOT.
Outputs of unchanged code cells are carried over; changed cells get empty outputs (notebook 3 outputs are filled by run_nb3.py).
"""
import ast, json, re, sys, textwrap, uuid
from pathlib import Path

SRC, ROOT = Path(sys.argv[1]), Path(sys.argv[2])
F = ["1_Planet_API_imagery_discovery.ipynb",
     "2_planet_sandbox_Para_BRA_sentinelhub.ipynb",
     "3_planet_sandbox_Para_BRA_sentinelhub_Analysis_NDVI.ipynb"]


def nid():
    return uuid.uuid4().hex[:8]


def md(text):
    text = textwrap.dedent(text).strip("\n")
    return {"cell_type": "markdown", "id": nid(), "metadata": {}, "source": text.splitlines(keepends=True)}


def code(src, old=None):
    """New code cell; `old` = an original code cell whose outputs are still valid (same behaviour, same prints)."""
    src = textwrap.dedent(src).strip("\n")
    return {"cell_type": "code", "id": nid(), "metadata": {},
            "execution_count": old.get("execution_count") if old and old.get("outputs") else None,
            "outputs": old.get("outputs", []) if old else [],
            "source": src.splitlines(keepends=True)}


def load(i):
    nb = json.load(open(SRC / F[i]))
    return nb, [c for c in nb["cells"] if c["cell_type"] == "code"], "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")


PIPELINE = "**Workflow:** 1 · Imagery discovery → 2 · Data preparation → 3 · NDVI analysis"


# ======================================================================================================= 1
def nb1():
    nb, old, alltext = load(0)
    ids = ast.literal_eval(re.search(r"REQUESTED_SCENE_IDS = (\[.*?\])", alltext, re.S).group(1))
    assert len(ids) == 76
    id_lines = "\n".join("    " + ", ".join(repr(i) for i in ids[k:k + 3]) + "," for k in range(0, len(ids), 3))
    cells = [
        md(f"""
        # 1 · Imagery discovery
        `1_Planet_API_imagery_discovery.ipynb` · {PIPELINE}

        Discover and inspect the Planet imagery that exists for the Pará area of interest (AOI) before anything is downloaded or analysed.

        - Authenticate with the Planet API
        - Define the area of interest
        - Search for available imagery
        - Inspect metadata, dates, cloud cover, assets and image availability
        - Identify suitable scenes or collections

        Separating discovery from processing makes it easier to verify that suitable data exist before downloading or analysing them.
        Searching metadata is free; downloading costs time and account quota.

        **Needs:** a Planet API key (typed at run time) · `pip install requests pandas` · **Output:** `all_images_values.csv`
        """),
        md("""
        ## 1.1 Authenticate
        The Data API uses HTTP Basic authentication: the API key is the user name, the password is empty.
        `getpass` keeps the key out of the notebook file, its outputs and Git. An empty key fails immediately instead of returning a confusing HTTP 401 later.
        """),
        code("""
        from getpass import getpass

        import pandas as pd
        import requests
        from IPython.display import Image, Markdown, display

        QUICK_SEARCH_URL = "https://api.planet.com/data/v1/quick-search"

        PLANET_API_KEY = getpass("Planet API key (input hidden): ").strip()
        if not PLANET_API_KEY:
            raise ValueError("An API key is required to query the Planet Data API.")
        """, old[1]),
        md("""
        ## 1.2 Area of interest
        A closed GeoJSON polygon in **longitude, latitude** order: the 568 km² rectangle `[-52.4825, -6.8735, -52.26725, -6.65775]` (west, south, east, north) taken from the Copernicus Data Space browser.
        """),
        code("""
        AOI = {
            "type": "Polygon",
            "coordinates": [[
                [-52.4825, -6.8735], [-52.4825, -6.65775],
                [-52.26725, -6.65775], [-52.26725, -6.8735],
                [-52.4825, -6.8735],
            ]],
        }
        """),
        md("""
        ## 1.3 Search for imagery
        The search is limited to the 76 scene IDs given for the task (2016-2026) **and** to scenes that intersect the AOI.
        All three Planet item types are listed because a scene ID only exists in one of them. A quick search answers in one request (no saved search needed); the timeout is 15 s to connect and 60 s to read.
        """),
        code("REQUESTED_SCENE_IDS = [\n" + id_lines + "\n]\n\n" + textwrap.dedent("""
        query = {
            "item_types": ["PSScene", "SkySatCollect", "PelicanScene"],
            "filter": {
                "type": "AndFilter",
                "config": [
                    {"type": "GeometryFilter", "field_name": "geometry", "config": AOI},
                    {"type": "StringInFilter", "field_name": "id", "config": REQUESTED_SCENE_IDS},
                ],
            },
        }

        response = requests.post(QUICK_SEARCH_URL, json=query, auth=(PLANET_API_KEY, ""), timeout=(15, 60))
        if response.status_code == 401:
            raise PermissionError("Planet rejected the API key (HTTP 401). Check the key and account access.")
        response.raise_for_status()

        features = response.json().get("features", [])
        print(f"Returned {len(features)} of {len(REQUESTED_SCENE_IDS)} requested scenes.")
        """), old[2]),
        md("""
        ## 1.4 Inspect metadata
        One row per scene: acquisition time, cloud cover, quality category, download permissions and links. `.get()` is used throughout because item types expose different properties.
        An empty result is reported as a message (check account access, key and AOI), not as an error.
        """),
        code("""
        records = []
        for feature in features:
            props, links = feature.get("properties", {}), feature.get("_links", {})
            records.append({
                "id": feature.get("id"),
                "item_type": feature.get("item_type") or props.get("item_type"),
                "acquired": props.get("acquired"),
                "cloud_percent": props.get("cloud_percent"),
                "cloud_cover": props.get("cloud_cover"),
                "quality_category": props.get("quality_category"),
                "thumbnail": links.get("thumbnail"),
                "item_url": links.get("_self"),
                "assets_url": links.get("assets"),
                "permissions": feature.get("_permissions"),
            })

        scenes = pd.DataFrame(records)
        if scenes.empty:
            display(Markdown("No scenes were returned for this AOI. Check account access, API key and AOI coordinates."))
        else:
            display(scenes.drop(columns=["thumbnail"]).sort_values("acquired", na_position="last").reset_index(drop=True))
        """, old[3]),
        md("""
        ## 1.5 Export the scene table
        Keeps `id`, `acquired`, `cloud_percent` and `quality_category` (`cloud_cover` is empty for every scene) and writes `all_images_values.csv`, which the Streamlit app's *Planet imagery (API)* tab can read.
        """),
        code("""
        df = scenes[["id", "acquired", "cloud_percent", "quality_category"]].copy()
        df["acquired"] = pd.to_datetime(df["acquired"])

        print(df.head())
        df.to_csv("all_images_values.csv", index=False)
        """, old[4]),
        md("""
        ## 1.6 Preview the scenes
        Shows one thumbnail per scene in the requested order, to judge visually which scenes are usable. IDs that were not returned are counted (outside the AOI or not available to the account).
        Thumbnails need the same key; they are displayed, not saved. If the acquisition time is missing, it is read from the scene ID (`YYYYMMDD_HHMMSS…`).
        """),
        code("""
        if not scenes.empty:
            selected = scenes.set_index("id", drop=False)
            missing = [i for i in REQUESTED_SCENE_IDS if i not in selected.index]
            if missing:
                print(f"{len(missing)} requested IDs were not returned by this search; they may be unavailable to this account or outside the AOI.")

            for scene_id in REQUESTED_SCENE_IDS:
                if scene_id not in selected.index:
                    continue
                row = selected.loc[scene_id]
                if isinstance(row, pd.DataFrame):  # duplicated id
                    row = row.iloc[0]
                if pd.isna(row["thumbnail"]) or not row["thumbnail"]:
                    print(f"Preview unavailable for {scene_id}: no thumbnail link was returned.")
                    continue

                acquired = pd.to_datetime(row["acquired"], utc=True, errors="coerce")
                if pd.notna(acquired):
                    title_time = acquired.strftime("%Y-%m-%d %H:%M:%S UTC")
                else:
                    try:
                        title_time = pd.to_datetime(scene_id[:15], format="%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S") + " (UTC, from scene ID)"
                    except ValueError:
                        title_time = "Acquisition time unavailable"

                display(Markdown(f"### {title_time} — {scene_id}"))
                try:
                    thumb = requests.get(row["thumbnail"], auth=(PLANET_API_KEY, ""), timeout=(15, 60))
                    thumb.raise_for_status()
                    display(Image(data=thumb.content, width=600))
                except requests.RequestException as exc:
                    print(f"Preview unavailable for {scene_id}: {exc}")
        """, old[5]),
    ]
    return nb, cells


# ======================================================================================================= 2
def nb2():
    nb, old, _ = load(1)
    cells = [
        md(f"""
        # 2 · Data preparation
        `2_planet_sandbox_Para_BRA_sentinelhub.ipynb` · {PIPELINE}

        Prepare consistent annual imagery for the Pará AOI.

        - Request or load imagery
        - Retrieve the relevant bands
        - Apply preprocessing
        - Create annual composites
        - Save the analysis-ready raster outputs

        Keeping data retrieval and preprocessing separate ensures that the analysis notebook receives standardized inputs.

        **Why Sentinel Hub and not `api.planet.com`:** the 2021-2023 sandbox collection (`PS_ARD_SR_DAILY`, analysis-ready PlanetScope surface reflectance) is hosted on Sentinel Hub.
        A Planet API key returns 404 there, so this notebook uses an **OAuth client** (Planet account → *OAuth Clients* → *Create New*; copy the secret immediately, it is shown once).
        The data are licensed CC-BY-NC, cover 2021-01-01 to 2023-12-29, and every download uses Processing Units from the account.

        **Needs:** `pip install requests pandas numpy rasterio` · **Outputs:** `all_images_sentinel.csv`, `planet_downloads/ARPS_Para_<date>.tif`, `composites/composite_<period>.tif`
        """),
        md("""
        ## 2.1 Setup
        """),
        code("""
        import time
        import warnings
        from getpass import getpass
        from pathlib import Path

        import numpy as np
        import pandas as pd
        import rasterio
        import requests
        from IPython.display import display
        from rasterio.windows import Window
        """),
        md("""
        ## 2.2 Settings
        Everything that defines *what* and *where* is set here once; later cells only use these names.

        - `BBOX`: the AOI as `[west, south, east, north]` in EPSG:4326.
        - `START_DATE` / `END_DATE`: deliberately wider than the collection, so the search returns exactly what exists.
        - `BANDS`: the four surface-reflectance bands, in this order in every file (red = band 3, NIR = band 4).
        - `WIDTH` / `HEIGHT`: 2400 px (Process API maximum 2500) over about 24 km ≈ 10 m per pixel; the native resolution is 3 m.
        - `STEP`: download every 7th available date to limit Processing Units and time.
        - `BASE_URL`: EU deployment. If the collection is not found, try `https://services-uswest2.sentinel-hub.com`.
        - Folders are relative to the notebook, so the project can be moved.
        """),
        code("""
        COLLECTION_ID = "3f605f75-86c4-411a-b4ae-01c896f0e54e"
        COLLECTION = f"byoc-{COLLECTION_ID}"

        BBOX = [-52.4825, -6.8735, -52.26725, -6.65775]
        BBOX_CRS = "http://www.opengis.net/def/crs/EPSG/0/4326"

        START_DATE = "2013-01-01T00:00:00Z"
        END_DATE = "2026-01-31T23:59:59Z"

        BANDS = ["blue", "green", "red", "nir"]
        WIDTH = HEIGHT = 2400
        STEP = 7

        BASE_URL = "https://services.sentinel-hub.com"

        OUTPUT_DIR = Path.cwd() / "planet_downloads"
        COMPOSITE_DIR = Path.cwd() / "composites"

        print("Collection:", COLLECTION)
        print("Date range:", START_DATE, "to", END_DATE)
        """, old[2]),
        md("""
        ## 2.3 Authenticate
        ### 2.3.1 Credentials
        Typed into hidden prompts and never printed. Empty values stop the run here rather than as a later HTTP 400.
        """),
        code("""
        CLIENT_ID = getpass("Planet OAuth client ID: ").strip()
        CLIENT_SECRET = getpass("Planet OAuth client secret: ").strip()

        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError("Client ID and secret are both required.")

        print("Credentials loaded.")
        """, old[3]),
        md("""
        ### 2.3.2 Access token
        The client ID and secret are exchanged for a short-lived bearer token. It is cached and renewed 60 s before it expires, so a long download cannot fail halfway.
        Requesting a token now shows a wrong secret immediately.
        """),
        code("""
        _token = {"value": None, "expires_at": 0.0}


        def get_token():
            \"\"\"Return a valid bearer token, fetching a new one only when needed.\"\"\"
            if _token["value"] and time.time() < _token["expires_at"] - 60:
                return _token["value"]

            r = requests.post(
                f"{BASE_URL}/auth/realms/main/protocol/openid-connect/token",
                data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
                timeout=60,
            )
            if not r.ok:
                print("Token request failed:", r.status_code)
                print(r.text[:1000])
                r.raise_for_status()

            data = r.json()
            _token["value"] = data["access_token"]
            _token["expires_at"] = time.time() + int(data.get("expires_in", 3600))
            return _token["value"]


        def auth_headers(**extra):
            return {"Authorization": f"Bearer {get_token()}", **extra}


        get_token()
        print("Authentication succeeded.")
        """, old[4]),
        md("""
        ## 2.4 Search the catalog
        ### 2.4.1 Find every date with imagery over the AOI
        The Catalog API lists scenes without returning pixels, so it costs no Processing Units.
        The two documented catalog paths are aliases; the second is tried only on a 404. Results come in pages of 100 (followed through `context.next`, at most 20 pages).
        """),
        code("""
        def catalog_search(body):
            r = None
            for path in ("/api/v1/catalog/1.0.0/search", "/catalog/v1/search"):
                r = requests.post(BASE_URL + path, headers=auth_headers(**{"Content-Type": "application/json"}),
                                  json=body, timeout=120)
                if r.status_code != 404:
                    break
            return r


        body = {"collections": [COLLECTION], "bbox": BBOX, "datetime": f"{START_DATE}/{END_DATE}", "limit": 100}
        features = []

        for page in range(20):
            r = catalog_search(body)
            if not r.ok:
                print("HTTP status:", r.status_code)
                print(r.text[:2000])
                if r.status_code == 401:
                    print("-> Credentials rejected. Check client ID/secret.")
                elif r.status_code == 403:
                    print("-> Account may lack access/Monitoring Credits for this collection.")
                elif r.status_code == 404:
                    print("-> Try the other deployment (BASE_URL in section 2.2).")
                r.raise_for_status()

            result = r.json()
            features.extend(result.get("features", []))
            next_page = result.get("context", {}).get("next")
            if not next_page:
                break
            body["next"] = next_page

        print("Returned features:", len(features))
        if not features:
            print("No scenes found. The collection covers 2021-01-01 to 2023-12-29; check the dates and that BBOX is inside the sandbox area.")
        """, old[5]),
        md("""
        ### 2.4.2 Summarise and save the catalog
        One row per scene with its timestamp, any cloud-related property (matched by the word "cloud", because the exact field name is not known in advance) and the date (`YYYY-MM-DD`), since downloads are requested per day.
        Saved as `all_images_sentinel.csv`: everything that is *available*, whether or not it is downloaded.
        """),
        code("""
        if not features:
            raise RuntimeError("No scenes found. See the message above.")

        rows = []
        for f in features:
            props = f.get("properties", {})
            row = {"id": f.get("id"), "datetime": props.get("datetime")}
            row.update({k: v for k, v in props.items() if "cloud" in k.lower()})
            rows.append(row)

        results_df = pd.DataFrame(rows)
        results_df["date"] = results_df["datetime"].str[:10]
        results_df.to_csv("all_images_sentinel.csv", index=False)

        print(f"{len(results_df)} images on {results_df['date'].nunique()} dates, {results_df['date'].min()} to {results_df['date'].max()}")
        display(results_df.head())
        """),
        md("""
        ## 2.5 Download the bands
        One GeoTIFF per selected date, saved as `ARPS_Para_<date>.tif` (analysis-ready PlanetScope, Pará).

        - **Bands and preprocessing:** the evalscript returns `BANDS` plus `dataMask` as 32-bit floats (so reflectance keeps its decimals). `dataMask` is the last band (1 = valid pixel), so each file has 5 bands.
        - **One request per day** with `mosaickingOrder: mostRecent` (if several scenes overlap, the most recent is on top), so every file is a clean snapshot of one date.
        - **Dates:** every `STEP`-th date plus the last one, so the series always spans the full period.
        - **Resumable:** existing files are skipped. The loop stops on HTTP 401/403/429 (credentials, permission or quota cannot be fixed by retrying) or any other error, and pauses 1 s between requests.
        """),
        code("""
        def build_evalscript(bands):
            names = list(bands) + ["dataMask"]
            inputs = ", ".join(f'"{b}"' for b in names)
            outputs = ", ".join(f"sample.{b}" for b in names)
            return f\"\"\"//VERSION=3
        function setup() {{
          return {{
            input: [{{ bands: [{inputs}] }}],
            output: {{ bands: {len(names)}, sampleType: "FLOAT32" }}
          }};
        }}
        function evaluatePixel(sample) {{
          return [{outputs}];
        }}
        \"\"\"


        def process_request(date):
            payload = {
                "input": {
                    "bounds": {"bbox": BBOX, "properties": {"crs": BBOX_CRS}},
                    "data": [{
                        "type": COLLECTION,
                        "dataFilter": {
                            "timeRange": {"from": f"{date}T00:00:00Z", "to": f"{date}T23:59:59Z"},
                            "mosaickingOrder": "mostRecent",
                        },
                    }],
                },
                "output": {
                    "width": WIDTH,
                    "height": HEIGHT,
                    "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
                },
                "evalscript": build_evalscript(BANDS),
            }
            headers = auth_headers(**{"Content-Type": "application/json", "Accept": "image/tiff"})
            return requests.post(f"{BASE_URL}/api/v1/process", headers=headers, json=payload, timeout=600)


        all_dates = sorted(results_df["date"].astype(str).unique())
        picked = all_dates[::STEP]
        if all_dates[-1] not in picked:
            picked.append(all_dates[-1])

        OUTPUT_DIR.mkdir(exist_ok=True)
        print(f"{len(all_dates)} dates in the catalog, {len(picked)} selected (every {STEP}th + the last).")

        downloaded, failed = [], []
        for date in picked:
            path = OUTPUT_DIR / f"ARPS_Para_{date}.tif"
            if path.exists() and path.stat().st_size > 0:
                print(date, "- already downloaded, skipping")
                downloaded.append(path)
                continue

            try:
                r = process_request(date)
            except Exception as error:
                failed.append(date)
                print(date, "- ERROR:", repr(error))
                break

            if r.ok:
                path.write_bytes(r.content)
                downloaded.append(path)
                print(date, "- saved", f"{path.stat().st_size:,}", "bytes")
            else:
                failed.append(date)
                print(date, "- FAILED", r.status_code, r.text[:500])
                if r.status_code in (401, 403, 429):
                    print("Stopping: authentication, permission or rate-limit error.")
                    break
            time.sleep(1)

        print(f"\\nDone. Downloaded: {len(downloaded)}, failed: {len(failed)}. Folder: {OUTPUT_DIR.name}/")
        if failed:
            print("Failed dates:", failed)
        """),
        md("""
        ## 2.6 Create annual composites
        Combines the per-date files into one image per period: `composite_2021.tif`, `composite_2022.tif`, `composite_2023.tif` and `composite_All_years.tif` (4 bands: blue, green, red, NIR; float32; NaN where no date has data).
        This is the input of notebook 3.

        - **Per-pixel median** over the dates: clouds, shadows and haze are extreme values on a single date, so the median ignores them without a cloud mask. The cost is that a composite mixes a whole year, so seasonal differences are averaged in.
        - **Only valid pixels count** (`dataMask` > 0), and dates with less than `MIN_COVERAGE` valid area are left out, because they would add almost no information.
        - **Processed in strips of `ROWS` rows**, so the full stack of dates never has to fit in memory.
        - **Existing composites are never overwritten.** Delete a file to rebuild it. Files are written under a temporary name first, so an interrupted run leaves no half-written composite.

        > The code that originally produced the composites in this project was not saved. This cell is a reconstruction (a median, which a comparison with the downloaded files supports) and has only been tested on small synthetic rasters.
        """),
        code("""
        MIN_COVERAGE = 0.10
        ROWS = 32


        def year_of(path):
            return path.stem.split("_")[-1][:4]


        def coverage(path):
            with rasterio.open(path) as src:
                return (src.read(src.count) > 0).mean()


        def median_composite(paths, out_path):
            with rasterio.open(paths[0]) as ref:
                profile, height, width = ref.profile, ref.height, ref.width
            for key in ("tiled", "blockxsize", "blockysize"):
                profile.pop(key, None)
            profile.update(count=len(BANDS), dtype="float32", nodata=np.nan, compress="deflate")

            tmp = out_path.with_name(out_path.stem + ".tmp.tif")
            with rasterio.open(tmp, "w", **profile) as dst:
                dst.descriptions = tuple(BANDS)
                for top in range(0, height, ROWS):
                    window = Window(0, top, width, min(ROWS, height - top))
                    stack = np.full((len(paths), len(BANDS), window.height, width), np.nan, dtype="float32")
                    for i, path in enumerate(paths):
                        with rasterio.open(path) as src:
                            data = src.read(window=window)
                        stack[i] = np.where(data[len(BANDS)] > 0, data[:len(BANDS)], np.nan)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        dst.write(np.nanmedian(stack, axis=0), window=window)
            tmp.replace(out_path)


        files = sorted(OUTPUT_DIR.glob("ARPS_Para_*.tif"))
        usable = [p for p in files if coverage(p) >= MIN_COVERAGE]
        print(f"{len(usable)} of {len(files)} downloaded dates have at least {MIN_COVERAGE:.0%} valid coverage.")

        COMPOSITE_DIR.mkdir(exist_ok=True)
        periods = {f"composite_{y}.tif": [p for p in usable if year_of(p) == y] for y in ("2021", "2022", "2023")}
        periods["composite_All_years.tif"] = usable

        for name, paths in periods.items():
            out_path = COMPOSITE_DIR / name
            if out_path.exists():
                print(name, "- exists, skipping (delete it to rebuild)")
            elif not paths:
                print(name, "- no usable images")
            else:
                print(name, f"- median of {len(paths)} images")
                median_composite(paths, out_path)
        """),
    ]
    return nb, cells


# ======================================================================================================= 3
def nb3():
    nb, old, _ = load(2)
    FUTURE = [
        "Compare images from the same months or seasons.",
        "Use monthly or quarterly time series instead of only annual composites.",
        "Add rainfall data.",
        "Add soil-moisture or soil-condition indicators.",
        "Add temperature and drought indicators.",
        "Add fire and burn-scar data.",
        "Add true-colour and false-colour composites.",
        "Add indices related to water, burn severity or vegetation stress.",
        "Add land-cover and protected-area layers.",
        "Compare results with official deforestation datasets (PRODES, DETER, MapBiomas).",
        "Add automated alerts for new change patches.",
        "Add confidence scores.",
        "Add field observations or validation points.",
        "Add cloud-probability and image-quality reporting.",
        "Add user-uploaded areas of interest.",
        "Add authenticated Planet API processing.",
        "Add scheduled data updates.",
        "Add historical time-series charts.",
        "Add automated PDF report generation on a schedule.",
        "Add a model to distinguish likely deforestation from seasonal or atmospheric effects.",
    ]
    cells = [
        md(f"""
        # 3 · NDVI analysis
        `3_planet_sandbox_Para_BRA_sentinelhub_Analysis_NDVI.ipynb` · {PIPELINE}

        Find where vegetation became less green between 2021 and 2023, how large that area is and whether it is concentrated in a few patches.

        - Calculate NDVI and NDVI change
        - Classify moderate and strong decreases or increases
        - Calculate area and percentage statistics
        - Identify connected change patches
        - Create graphs, maps and exports

        This notebook performs the analytical and interpretive work. Separating it from data discovery and preprocessing makes the workflow easier to test, explain, reproduce and reuse.

        **Needs:** the four composites from notebook 2 in `composites/` · `pip install numpy pandas rasterio scipy matplotlib`
        **Outputs:** `composites/ndvi_statistics.csv`, `composites/change_classes.csv`, `composites/decline_patches.csv` and the figures below.
        **NDVI** = (NIR − Red) / (NIR + Red). Bands in every composite: 1 blue, 2 green, 3 red, 4 NIR.
        """),
        md("""
        ## 3.1 Load the composites
        All four composites are read into memory as 32-bit floats (enough precision for ratios, half the memory of 64-bit). Missing periods are reported and skipped, but the *All years* composite is required: it sets the colour stretch in section 3.3.
        `DISPLAY_STEP` shows at most about 1200 pixels across in the figures; calculations always use the full resolution.
        """),
        code("""
        from pathlib import Path

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import rasterio
        from matplotlib.patches import Rectangle
        from scipy import ndimage

        COMPOSITE_DIR = Path.cwd() / "composites"
        FILES = {
            "2021": "composite_2021.tif",
            "2022": "composite_2022.tif",
            "2023": "composite_2023.tif",
            "All years": "composite_All_years.tif",
        }

        composites = {}
        for name, file in FILES.items():
            path = COMPOSITE_DIR / file
            if not path.exists():
                print("Missing:", file)
                continue
            with rasterio.open(path) as src:
                composites[name] = src.read().astype("float32")
                bounds, pixel_size = src.bounds, src.res
                print(f"{name}: shape {composites[name].shape}, CRS {src.crs.to_string()}")

        if "All years" not in composites:
            raise FileNotFoundError("composite_All_years.tif not found. Run notebook 2 (section 2.6) first.")

        DISPLAY_STEP = max(1, composites["All years"].shape[2] // 1200)
        """),
        md("""
        ## 3.2 Check the data
        Pixel-by-pixel comparison is only valid if all composites share size, CRS and extent, so they are compared in one table before any analysis. `valid_%` is the share of pixels with data (from the GeoTIFF mask).
        Per-band statistics help to spot a band full of zeros or a shifted scale.
        """),
        code("""
        summary = []
        for name, file in FILES.items():
            path = COMPOSITE_DIR / file
            if not path.exists():
                summary.append({"composite": name, "status": "missing"})
                continue
            with rasterio.open(path) as src:
                summary.append({
                    "composite": name,
                    "size": f"{src.width} x {src.height}",
                    "bands": src.count,
                    "crs": src.crs.to_string(),
                    "pixel_size_deg": round(src.res[0], 8),
                    "dtype": src.dtypes[0],
                    "valid_%": round((src.dataset_mask() > 0).mean() * 100, 3),
                })
        display(pd.DataFrame(summary))

        BAND_NAMES = ["blue", "green", "red", "nir"]
        band_stats = []
        for name, arr in composites.items():
            for i, band in enumerate(BAND_NAMES):
                v = arr[i][np.isfinite(arr[i])].astype("float64")
                band_stats.append({"composite": name, "band": band, "min": v.min(), "mean": v.mean(),
                                   "median": np.median(v), "max": v.max(), "std": v.std()})
        display(pd.DataFrame(band_stats).round(1))
        """),
        md("""
        ## 3.3 True-colour view
        A visual sanity check. The *All years* composite defines **one** contrast stretch (2nd-98th percentile per band, from every 10th pixel) used for all panels, so differences between years are not hidden or invented by separate stretches.
        The file order is blue, green, red; the display order is red, green, blue.
        """),
        code("""
        ref = composites["All years"]
        limits = {}
        for i in (0, 1, 2):
            values = ref[i][np.isfinite(ref[i])][::10]
            low, high = np.percentile(values, [2, 98])
            limits[i] = (low, high if high != low else low + 1e-6)


        def to_rgb(arr):
            channels = []
            for i in (2, 1, 0):
                low, high = limits[i]
                scaled = np.clip((arr[i, ::DISPLAY_STEP, ::DISPLAY_STEP] - low) / (high - low), 0, 1)
                channels.append(np.nan_to_num(scaled))
            return np.dstack(channels)


        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        for ax, name in zip(axes.ravel(), FILES):
            if name in composites:
                ax.imshow(to_rgb(composites[name]), interpolation="nearest")
                ax.set_title(f"True colour: {name}")
            else:
                ax.set_title(f"{name}: missing")
            ax.axis("off")
        plt.tight_layout()
        plt.show()
        """),
        md("""
        ## 3.4 NDVI
        ### 3.4.1 Calculate NDVI and its statistics
        NDVI is a ratio, so it does not depend on whether reflectance is scaled. Pixels with `NIR + Red = 0` become **NaN**, never 0, so empty pixels are not mistaken for "no vegetation".
        The table gives the number of valid pixels, mean, median and 5th/95th percentile per period (percentiles show the spread without being dominated by a few extremes) and is saved unrounded to `ndvi_statistics.csv`.
        Values near 0.8-0.9 are typical of dense tropical forest, where NDVI saturates.
        """),
        code("""
        def ndvi_of(arr):
            red, nir = arr[2], arr[3]
            with np.errstate(divide="ignore", invalid="ignore"):
                return (nir - red) / (nir + red)


        ndvis = {name: ndvi_of(arr) for name, arr in composites.items()}

        statistics = []
        for name, ndvi in ndvis.items():
            v = ndvi[np.isfinite(ndvi)]
            statistics.append({
                "period": name,
                "valid_pixels": len(v),
                "mean_ndvi": v.mean(),
                "median_ndvi": np.median(v),
                "p05_ndvi": np.percentile(v, 5),
                "p95_ndvi": np.percentile(v, 95),
            })

        statistics_df = pd.DataFrame(statistics)
        print(statistics_df.round(3).to_string(index=False))
        statistics_df.to_csv(COMPOSITE_DIR / "ndvi_statistics.csv", index=False)
        """),
        md("""
        ### 3.4.2 NDVI maps
        Same colour scale for every panel (−0.2 to 1) so panels are comparable: below 0 is mostly water, cloud or shadow; above 0.8 is dense vegetation.
        The change map is 2023 − 2021 (the longest span available) on a symmetric scale: white = no change, red = loss, blue = gain.
        """),
        code("""
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        for ax, (name, ndvi) in zip(axes.ravel(), ndvis.items()):
            im = ax.imshow(ndvi[::DISPLAY_STEP, ::DISPLAY_STEP], cmap="RdYlGn", vmin=-0.2, vmax=1)
            ax.set_title(f"NDVI: {name}")
            ax.axis("off")
            fig.colorbar(im, ax=ax, fraction=0.046, label="NDVI")
        plt.tight_layout()
        plt.show()

        diff = ndvis["2023"] - ndvis["2021"]
        plt.figure(figsize=(9, 8))
        plt.imshow(diff[::DISPLAY_STEP, ::DISPLAY_STEP], cmap="RdBu", vmin=-0.5, vmax=0.5)
        plt.colorbar(label="NDVI change (2023 - 2021)")
        plt.title("Vegetation change 2021 to 2023 (red = loss, blue = gain)")
        plt.axis("off")
        plt.show()
        """),
        md("""
        ## 3.5 NDVI change classes
        ### 3.5.1 Classify, count and measure
        `change` = NDVI 2023 − NDVI 2021, only for pixels valid in **both** years (all others stay NaN). Negative = decline.
        Pixels are split into five classes with two thresholds: **moderate ≥ 0.10** (above year-to-year noise) and **strong ≥ 0.20** (a clear drop, e.g. 0.85 → 0.65). The classes do not overlap and add up to the valid pixels.
        Percentages use valid pixels as the denominator. Area uses the pixel size at the AOI's central latitude (a degree of longitude shrinks with the cosine of latitude), which is accurate to well under 1 % for an area this small.
        """),
        code("""
        MODERATE, STRONG = 0.10, 0.20

        ndvi_2021, ndvi_2023 = ndvis["2021"], ndvis["2023"]
        valid = np.isfinite(ndvi_2021) & np.isfinite(ndvi_2023)
        change = np.full(valid.shape, np.nan, dtype="float32")
        change[valid] = ndvi_2023[valid] - ndvi_2021[valid]

        mid_lat = (bounds.top + bounds.bottom) / 2
        pixel_ha = (pixel_size[0] * 111_320 * np.cos(np.radians(mid_lat))) * (pixel_size[1] * 110_574) / 10_000

        classes = {
            f"Strong decrease (≤ -{STRONG:.2f})": change <= -STRONG,
            f"Moderate decrease (-{STRONG:.2f} to -{MODERATE:.2f})": (change <= -MODERATE) & (change > -STRONG),
            f"Little change (|Δ| < {MODERATE:.2f})": np.abs(change) < MODERATE,
            f"Moderate increase ({MODERATE:.2f} to {STRONG:.2f})": (change >= MODERATE) & (change < STRONG),
            f"Strong increase (≥ {STRONG:.2f})": change >= STRONG,
        }

        n_valid = int(valid.sum())
        class_df = pd.DataFrame({
            "class": list(classes),
            "pixels": [int(m.sum()) for m in classes.values()],
        })
        class_df["% of valid"] = (class_df["pixels"] / n_valid * 100).round(2)
        class_df["area_ha"] = (class_df["pixels"] * pixel_ha).round(1)

        print(f"Valid pixels in both years: {n_valid:,} ({n_valid * pixel_ha / 100:,.0f} km²), pixel ≈ {pixel_ha * 10_000:.0f} m²")
        print(class_df.to_string(index=False))
        class_df.to_csv(COMPOSITE_DIR / "change_classes.csv", index=False)
        """),
        md("""
        ### 3.5.2 Map the decline
        Two binary maps: pixels with a decline of at least 0.10 (moderate **or** strong) and at least 0.20 (strong only).
        """),
        code("""
        decline_010 = valid & (change <= -MODERATE)
        decline_020 = valid & (change <= -STRONG)

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for ax, mask, threshold in ((axes[0], decline_010, MODERATE), (axes[1], decline_020, STRONG)):
            ax.imshow(mask[::DISPLAY_STEP, ::DISPLAY_STEP], cmap="Reds", vmin=0, vmax=1)
            ax.set_title(f"NDVI decline ≥ {threshold:.2f}\\n{mask.sum() / n_valid:.2%} of valid pixels")
            ax.axis("off")
        plt.tight_layout()
        plt.show()
        """),
        md("""
        ## 3.6 Decline patches
        ### 3.6.1 Find connected patches
        The raw strong-decline mask contains isolated specks and 1-pixel gaps that are noise. A morphological **opening** (removes specks smaller than 3×3 px) followed by a **closing** (fills 1-px holes, so one clearing is not split) cleans it; the order matters, because closing first would join the specks.
        `ndimage.label` then numbers each connected group of pixels (4-connectivity: pixels must share an edge; the Streamlit app counts diagonal neighbours too, so it reports slightly fewer patches).
        Patches of at least **100 pixels (≈ 1 ha)** are kept as large patches, a common minimum for mapping forest loss. The table is saved to `decline_patches.csv`.
        """),
        code("""
        MIN_PIXELS = 100
        kernel = np.ones((3, 3))

        decline_clean = ndimage.binary_opening(decline_020, structure=kernel)
        decline_clean = ndimage.binary_closing(decline_clean, structure=kernel)

        labels, n_patches = ndimage.label(decline_clean)
        patch_sizes = np.bincount(labels.ravel())[1:]
        large_patch_ids = np.flatnonzero(patch_sizes >= MIN_PIXELS) + 1

        print("Total decline patches:", n_patches)
        print(f"Patches with at least {MIN_PIXELS} pixels:", len(large_patch_ids))
        print("Largest patch size:", patch_sizes.max() if len(patch_sizes) else 0, "pixels")

        centres = ndimage.center_of_mass(decline_clean, labels, large_patch_ids)
        patch_df = pd.DataFrame({
            "patch_id": large_patch_ids,
            "pixels": patch_sizes[large_patch_ids - 1],
            "area_ha": (patch_sizes[large_patch_ids - 1] * pixel_ha).round(2),
            "center_lon": [bounds.left + (c + 0.5) * pixel_size[0] for _, c in centres],
            "center_lat": [bounds.top - (r + 0.5) * pixel_size[1] for r, _ in centres],
        }).sort_values("pixels", ascending=False)

        patch_df.to_csv(COMPOSITE_DIR / "decline_patches.csv", index=False)
        display(patch_df.head(10).round(5))
        """),
        md("""
        ### 3.6.2 Outline the large patches
        Each yellow rectangle is the **smallest rectangle containing one large patch** (`ndimage.find_objects`); the red area is the cleaned decline mask; the label is the patch ID and its size in pixels.
        A rectangle can contain pixels that are not part of the patch. If 55 boxes are too many, outline only the largest, e.g. `large_patch_ids[np.argsort(patch_sizes[large_patch_ids - 1])[-10:]]`.
        """),
        code("""
        objects = ndimage.find_objects(labels)

        fig, ax = plt.subplots(figsize=(12, 10))
        ax.imshow(decline_clean, cmap="Reds", vmin=0, vmax=1)

        for patch_id in large_patch_ids:
            rows, cols = objects[patch_id - 1]
            ax.add_patch(Rectangle((cols.start, rows.start), cols.stop - cols.start, rows.stop - rows.start,
                                   fill=False, edgecolor="yellow", linewidth=1.5))
            ax.text(cols.start, rows.start, f"ID {patch_id}\\n{patch_sizes[patch_id - 1]} px",
                    color="white", fontsize=8, backgroundcolor="black")

        ax.set_title("NDVI decline ≥ 0.20 with large patch boxes")
        ax.axis("off")
        plt.tight_layout()
        plt.show()
        """),
        md("""
        ## 3.7 Interpretation and limits
        - NDVI change marks **areas to investigate, not confirmed deforestation**. A drop can also come from seasonality, clouds, fire, drought, flooding or harvest.
        - The annual composites mix different acquisition dates and seasons; comparing images from the same months would be stronger evidence.
        - The thresholds (0.10, 0.20) and the 1 ha minimum patch size are analyst choices; the reported area moves with them.
        - Dense forest saturates NDVI near 0.8-0.9, so NDVI detects clearing better than degradation inside closed forest.
        - Three annual points describe a change, not a statistical trend.
        """),
        md("## 3.8 Future scope\n\nWith better data (denser, cloud-masked time series, matching seasons, rainfall and ground validation) this analysis could do much more:\n\n"
           + "\n".join(f"- {t}" for t in FUTURE)
           + "\n\n*Each of these would require additional data, validation and processing time; none is implied by the current results.*"),
    ]
    return nb, cells


for i, b in enumerate((nb1, nb2, nb3)):
    nb, cells = b()
    nb["cells"] = cells
    nb["nbformat"], nb["nbformat_minor"] = 4, 5
    with open(ROOT / F[i], "w") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(F[i], len(cells), "cells,", sum(c["cell_type"] == "code" for c in cells), "code")
