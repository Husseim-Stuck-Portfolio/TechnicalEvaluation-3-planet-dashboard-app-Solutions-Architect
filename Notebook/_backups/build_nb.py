"""Rebuild the three notebooks as ONE numbered workbook (Part 1-3).

Rule: code cells are copied byte-for-byte from the untouched originals in _backups/ (source, outputs, execution_count,
metadata). Only markdown cells are replaced/added. Re-running this script is idempotent because it always starts from the backups.
"""
import json, sys, textwrap, uuid
from pathlib import Path

ROOT = Path(sys.argv[1])
SRC = ROOT / "_backups"
FILES = ["1_Planet_API_imagery_discovery.ipynb",
         "2_planet_sandbox_Para_BRA_sentinelhub.ipynb",
         "3_planet_sandbox_Para_BRA_sentinelhub_Analysis_NDVI.ipynb"]


def md(text):
    text = textwrap.dedent(text).strip("\n")
    return {"cell_type": "markdown", "id": uuid.uuid4().hex[:8], "metadata": {}, "source": text.splitlines(keepends=True)}


def load(i):
    nb = json.load(open(SRC / FILES[i]))
    codes = [c for c in nb["cells"] if c["cell_type"] == "code"]
    for c in codes:                                   # nbformat 4.5 wants ids; adding one never touches the code
        c.setdefault("id", uuid.uuid4().hex[:8])
    return nb, codes


MAP = """
| Part | Notebook file | Job | Main output |
|---|---|---|---|
| **1** | `1_Planet_API_imagery_discovery.ipynb` | Discover and inspect Planet imagery with the Planet Data API | `all_images_values.csv` |
| **2** | `2_planet_sandbox_Para_BRA_sentinelhub.ipynb` | Search the Planet sandbox on Sentinel Hub and download one analysis-ready GeoTIFF per date | `all_images_sentinel.csv`, `planet_downloads/ARPS_Para_<date>.tif` |
| **3** | `3_planet_sandbox_Para_BRA_sentinelhub_Analysis_NDVI.ipynb` | Read the annual composites, calculate NDVI, NDVI change and decline patches | `composites/ndvi_statistics.csv` and figures |
"""

CONVENTIONS = """
**Conventions used in all three parts**

- **Numbering.** `Part N` is one notebook file; `N.k` is a section; `N.k.j` is a sub-section. Numbers are continuous inside a part, so the three files read as one document.
- **Code is never edited by this documentation.** Every code cell is exactly as it was written; the explanations sit in the markdown cells around it.
- **Credentials** (Planet API key, OAuth client ID/secret) are typed at run time with `getpass`, so they never appear in a file, an output or the repository.
- **Area of interest (AOI).** One rectangle in Pará, Brazil, `[west, south, east, north] = [-52.4825, -6.8735, -52.26725, -6.65775]` (EPSG:4326, longitude/latitude, about 568 km²), taken from the Copernicus Data Space Ecosystem browser. Part 1 writes it as a GeoJSON polygon, Parts 2 and 3 as a bounding box.
- **Band order** of every GeoTIFF used from Part 2 on: 1 = Blue, 2 = Green, 3 = Red, 4 = NIR, and (in the per-date downloads only) 5 = `dataMask` (1 = valid pixel). NDVI therefore uses band 3 (red) and band 4 (NIR).
- **NDVI** = (NIR − Red) / (NIR + Red). It is a ratio, so it does not depend on whether reflectance is stored as 0-1 or as DN/10000.
- **Run order.** Run each part top to bottom after restarting the kernel. Parts 2 and 3 do not need Part 1 to be re-run; Part 3 needs the files that Part 2 and the composite step (section 2.11) produced.
"""


# =============================================================================================== PART 1
def part1():
    nb, c = load(0)
    cells = [
        md("""
        # Planet Forest-Change Workflow: Part 1 of 3 · Imagery discovery
        **Study area:** Pará, North Region, Brazil · **Period of interest:** 2021-2023 (scene IDs span 2016-2026)

        This is the first of three notebooks that are written to be read as **one workbook**:
        """),
        md(MAP), md(CONVENTIONS),
        md("""
        ## 1.1 Purpose of Part 1

        Part 1 answers one question *before* any heavy processing happens: **does Planet have usable imagery over the area of interest, and what does it look like?**
        It searches the Planet Data API for a curated list of scene IDs, tabulates their metadata (acquisition time, cloud cover, quality, permissions), exports that table
        as a CSV, and shows a thumbnail of every scene.

        **Why a separate discovery step?** Searching metadata is free and fast, while downloading and processing imagery costs time and account quota (see Part 2).
        Checking first that suitable scenes exist avoids paying for data that turns out to be cloudy, outside the area or not licensed to the account.

        **Inputs:** a Planet API key (typed at run time) · the AOI polygon · the 76 requested scene IDs.
        **Outputs:** `all_images_values.csv` (one row per scene) and on-screen previews. Nothing else is written to disk, and no imagery is downloaded.
        """),
        md("""
        ## 1.2 Environment and connection

        ### 1.2.1 Install the Planet client package
        The next cell is written as `#! pip install planet`. Because it starts with `#`, Python treats it as a **comment** and does not run it; it is a reminder of which package belongs to this account workflow.
        The code below does **not** import the `planet` package: it talks to the API directly with `requests`. That is a deliberate choice: plain HTTP calls make every request visible and easy to explain,
        and need no extra dependency beyond `requests` and `pandas`. Remove the `#` only if you want the official SDK for your own experiments.
        """),
        c[0],
        md("""
        ### 1.2.2 Imports, API key and area of interest
        **What the cell below does, and why:**

        | Choice | Reason |
        |---|---|
        | `from getpass import getpass` and `getpass('Planet API key (input hidden): ')` | The key is typed into a hidden prompt, so it is never written into the notebook file, its outputs or Git. |
        | `if not PLANET_API_KEY.strip(): raise ValueError(...)` | **Fail fast.** An empty key would only produce a confusing HTTP 401 later; this gives a clear message immediately. |
        | `requests` | A simple, explicit HTTP client; the Data API is a normal REST API. |
        | `pandas` | Turns the JSON answer into a table that can be sorted, displayed and exported. |
        | `IPython.display` (`display`, `Markdown`, `Image`) | Used to render headings and thumbnails inside the notebook. |
        | `QUICK_SEARCH_URL = https://api.planet.com/data/v1/quick-search` | The Data API's **quick search** endpoint answers a search immediately from a JSON body. A *saved* search would need extra create/fetch calls that this one-off query does not need. |
        | `AOI` as a GeoJSON `Polygon` | The Data API filters by geometry in GeoJSON. Coordinates are **longitude, latitude** (not latitude, longitude), and the ring is **closed** (first point = last point). The four corners are the AOI rectangle from the Copernicus Data Space browser. |

        **Authentication:** the Data API uses HTTP Basic authentication with the *API key as the username and an empty password*. The Planet account e-mail/password is not used here.
        """),
        c[1],
        md("""
        ## 1.3 Search for the requested scenes

        ### 1.3.1 Build and send the query
        **What the cell below does, and why:**

        - `REQUESTED_SCENE_IDS` is the list of **76 scene IDs** given for this task, spanning 2016-2026. Searching by ID (instead of "everything between two dates") returns exactly the scenes the evaluation asked about.
          Scene IDs begin with the acquisition time `YYYYMMDD_HHMMSS`, which is also used as a fallback in section 1.5.
        - `item_types = ['PSScene', 'SkySatCollect', 'PelicanScene']`: Planet's three imagery families (PlanetScope ≈ 3 m, SkySat ≈ 0.5 m, Pelican, the newest constellation). A scene ID only exists in one family, but the Data API needs the family names in the request, so all three are listed rather than guessing.
        - `AndFilter` = **GeometryFilter** (scene must intersect the AOI) **AND** **StringInFilter** on `id` (scene must be one of the 76). Both conditions together mean "these scenes, and only where they touch the AOI".
        - `requests.post(..., json=query, auth=(PLANET_API_KEY, ''), timeout=(15, 60))`: `json=` sends the body as JSON; `auth=(key, '')` is the Basic-auth pattern above; `timeout=(15, 60)` means 15 s to connect and 60 s to read, so a network problem cannot freeze the notebook.
        - **HTTP 401** gets its own `PermissionError` with a human-readable hint; any other error status is raised by `raise_for_status()`.
        - `features = payload.get('features', [])`: the matching scenes are GeoJSON *features*. `.get(..., [])` returns an empty list instead of crashing if the key is missing.
        - The final `print` compares **returned vs requested**. A smaller number is normal and tells you some scenes are outside the AOI or not available to the account (section 1.5 lists which).
        - **No pagination loop** is needed: a quick search returns up to 250 results per page and only 76 IDs are requested.
        """),
        c[2],
        md("""
        ## 1.4 Review and export the scene metadata

        ### 1.4.1 Flatten the JSON answer into a table
        **Why `.get()` everywhere:** different item types expose different properties, so a missing field must give `None`, not an error.
        **Fields kept and why:**

        | Column | Meaning / use |
        |---|---|
        | `id`, `item_type` | Identify the scene and its family (`item_type` is read from the feature or, if absent, from `properties`). |
        | `acquired` | Acquisition time (UTC) - needed for every time-based chart. |
        | `cloud_percent`, `cloud_cover` | Two cloud fields exist in Planet's schema (percent 0-100 and fraction 0-1). Both are kept so the next step can show which one is actually filled. |
        | `quality_category` | Planet's "standard / test" quality flag. |
        | `thumbnail`, `item_url`, `assets_url` | Links used later to preview, inspect or order the scene. |
        | `permissions` | Shows whether the account is entitled to download the scene. |

        If the table is empty the cell prints a message (account access, API key, AOI) instead of raising: in a *discovery* notebook, "nothing found" is a result, not a crash.
        The table is shown **sorted by acquisition time** (`na_position='last'`) and **without the `thumbnail` column**, because the long URLs would make the display unreadable; the column stays in the DataFrame for section 1.5.
        """),
        c[3],
        md("""
        ### 1.4.2 Export the compact table (`all_images_values.csv`)
        - `pd.to_datetime(df["acquired"])` converts the text timestamps into real datetimes so they can be sorted and grouped by month or year.
        - Only four columns are kept: `id`, `acquired`, `cloud_percent`, `quality_category`. The comment in the code explains why `cloud_cover` is dropped: **it is `None` for every scene**, so it carries no information.
        - `to_csv(..., index=False)` writes the file without the meaningless row numbers. This CSV is the offline input of the Streamlit app's *Planet imagery (API)* tab (columns `id`, `acquired`, `cloud_percent`).
        - `pandas` is imported again at the top of the cell. That repeat is harmless and lets the cell run on its own after a kernel restart; it is left unchanged on purpose.
        """),
        c[4],
        md("""
        ## 1.5 Display the requested previews

        ### 1.5.1 Fetch and show one thumbnail per scene
        **Decisions in the cell below:**

        - **Requested order is kept** (`for scene_id in REQUESTED_SCENE_IDS if ...`), so the gallery follows the task's list, not the order Planet happened to return.
        - **Missing IDs are counted and reported** instead of silently skipped, because they are informative: the scene may be outside the AOI or not available to this account.
        - `isinstance(row, pd.DataFrame): row = row.iloc[0]` guards against duplicated IDs: pandas returns a table instead of a single row in that case.
        - **Scenes without a thumbnail link** are announced and skipped.
        - **Title time:** the acquisition time from the metadata (converted to UTC); if it is missing, the timestamp inside the scene ID (`YYYYMMDD_HHMMSS`) is used and labelled "from scene ID", so the reader always knows where the time came from.
        - **Thumbnails need the same Basic-auth key** as the search, so the image request repeats `auth=(PLANET_API_KEY, '')`. `timeout=(15, 60)` and `raise_for_status()` protect against hangs and bad responses; a `RequestException` for one image is printed and the loop continues, so one failed preview does not stop the rest.
        - Images are **displayed, not saved** (`Image(data=..., width=600)`). Discovery only needs to *see* the scenes; not writing them to disk also respects the licence of the imagery.
        """),
        c[5],
        md("""
        ## 1.6 What Part 1 gives to Part 2

        - A table of scene metadata (`all_images_values.csv`) that shows when imagery exists, how cloudy it is and whether the account may use it.
        - Confidence that the AOI, the API key and the scene list are valid.
        - **Hand-over:** the 2021-2023 data is *not* downloaded from `api.planet.com`. The analysis-ready sandbox collection lives on **Sentinel Hub**, which needs a different login (OAuth client). Part 2 explains why and does the download.

        **Limits of Part 1:** cloud cover is a scene-level number (a single value for a whole scene), so a "clear" scene can still be cloudy over this particular AOI; previews are low-resolution thumbnails, not analysis data.
        """),
    ]
    return nb, cells


# =============================================================================================== PART 2
def part2():
    nb, c = load(1)
    cells = [
        md("""
        # Planet Forest-Change Workflow: Part 2 of 3 · Data preparation (Planet sandbox via Sentinel Hub)
        **You are in Part 2 of 3.** Part 1 found out *what* imagery exists; Part 2 searches the analysis-ready sandbox collection and **downloads one GeoTIFF per acquisition date**; Part 3 turns the annual composites into NDVI and change maps.
        Conventions (numbering, band order, credentials, AOI) are listed at the top of Part 1.
        """),
        md("""
        ## 2.1 Purpose and background

        **Why this is a different service from Part 1.** The sandbox collection (`byoc-3f605f75-86c4-411a-b4ae-01c896f0e54e`, source `PS_ARD_SR_DAILY`, "analysis-ready PlanetScope surface reflectance") is hosted on **Sentinel Hub** (`services.sentinel-hub.com`), not on `api.planet.com`.
        A Planet API key only works with `api.planet.com`; asking Sentinel Hub for the collection with that key returns **404**. This is why Part 2 authenticates with an **OAuth client ID + secret** instead.

        **What Part 2 does**
        1. Authenticates with the OAuth client (sections 2.4-2.5).
        2. Searches the **Catalog API** for every date that has imagery over the AOI and saves that list (sections 2.6-2.7).
        3. Downloads GeoTIFFs with the **Process API** (sections 2.9-2.10). There is no "asset activation" step as in the Data API: the Process API renders the pixels on request.
        4. Explains how the per-date files become annual composites (section 2.11).

        **Before running (one time)**
        1. Open the Planet Account app (`insights.planet.com/account`) → **OAuth Clients** → **Create New**.
        2. Copy the **client ID** and **client secret** immediately (the secret is shown only once).
        3. The account needs Monitoring Credits (paid or trial). The sandbox data are licensed **CC-BY-NC** (non-commercial).

        The collection covers **2021-01-01 to 2023-12-29** around (-6.77, -52.38). Every Process request consumes *Processing Units* from the account, which is why the notebook downloads sparingly (section 2.10).
        The secret is never pasted into a cell; it is requested with `getpass`.
        """),
        md("""
        ## 2.2 Environment

        ### 2.2.1 Install packages
        The line `#%pip install requests pandas rasterio matplotlib numpy` is a comment (it starts with `#`), so it does not run; it lists what must be installed once.
        `requests` = HTTP, `pandas` = tables, `numpy` = arrays, `rasterio` = reading GeoTIFFs (used in Part 3 and handy for checking downloads), `matplotlib` = plots. Uncomment the line only if one of them is missing.
        """),
        c[0],
        md("""
        ### 2.2.2 Imports
        `json` (pretty-print API properties), `time` (token expiry and polite pauses), `Path` (file paths that work on macOS, Linux and Windows), `getpass` (hidden credential prompts), `numpy`, `pandas`, `requests`.
        All imports are kept together in this one cell so the rest of the part reads without hidden dependencies.
        """),
        c[1],
        md("""
        ## 2.3 Settings
        **Every constant that defines "what and where" lives in this one cell, so nothing is hidden inside the logic below.**

        | Setting | Value | Why |
        |---|---|---|
        | `COLLECTION_ID` / `COLLECTION` | `3f605f75-…` → `byoc-3f605f75-…` | The sandbox collection ID from the Planet account; Sentinel Hub names user collections **BYOC** ("bring your own COG"), hence the `byoc-` prefix. |
        | `BBOX` | `[-52.4825, -6.8735, -52.26725, -6.65775]` | West, south, east, north in EPSG:4326: the AOI of Part 1 as a rectangle (the Catalog and Process APIs accept a bounding box directly). |
        | `START_DATE` / `END_DATE` | 2013-01-01 → 2026-01-31 | Deliberately **wider** than the data. The collection only holds 2021-01-01 → 2023-12-29, so the search returns exactly what exists without having to know the edge dates. |
        | `WIDTH` / `HEIGHT` | 2400 × 2400 | The Process API allows at most 2500 × 2500 pixels. 2400 px across ≈ 24 km gives **≈ 10 m per pixel**, a balance between detail and request cost. The native resolution is ≈ 3 m; a smaller `BBOX` is needed to use it. |
        | `BASE_URL` | `https://services.sentinel-hub.com` | The EU deployment, where the Planet sandbox normally lives. The comment lists the US-West deployment to try if authentication or search says the collection does not exist. |
        """),
        c[2],
        md("""
        ## 2.4 Credentials

        ### 2.4.1 Enter the OAuth client (private)
        `getpass` hides what you type. `.strip()` removes accidental spaces or line breaks from copy-paste, a frequent cause of "invalid client" errors. The cell **refuses to continue if either value is empty** (clear error now rather than an HTTP 400 later) and prints only "Credentials loaded", never the values.
        """),
        c[3],
        md("""
        ## 2.5 Authentication

        ### 2.5.1 Get and cache an access token
        Sentinel Hub uses the OAuth **client-credentials** flow: the client ID and secret are exchanged for a short-lived *bearer token* that is sent with every request.

        - `_token = {"value": None, "expires_at": 0.0}`: a small dictionary acts as a cache. A dictionary is mutable, so the function can update it without a `global` statement.
        - `get_token()` reuses the token while it is still valid and asks for a new one **60 seconds before** the stated expiry, so a long download cannot fail halfway because the token ran out.
        - On failure it prints the HTTP status and the first 1000 characters of the answer (enough to read the reason, short enough not to flood the screen), then `raise_for_status()` stops the run. The secret itself is never printed.
        - `expires_in` falls back to 3600 s if the server does not send it.
        - `auth_headers(**extra)` builds the `Authorization: Bearer …` header and merges extra headers (for example `Content-Type`), so every later call needs one line.
        - The last two lines request a token immediately so a wrong secret is discovered **now**, not in the middle of the search.
        """),
        c[4],
        md("""
        ## 2.6 Search the catalog

        ### 2.6.1 List every date with imagery over the AOI
        The **Catalog API** answers "which scenes exist?" without returning pixels (so it costs no Processing Units).

        - `catalog_search(body)` tries the two documented paths `/api/v1/catalog/1.0.0/search` and `/catalog/v1/search`. They are aliases; the second is only used if the first answers **404**, which keeps the notebook working on deployments that expose only one of them.
        - `body`: `collections` (which collection), `bbox` (where), `datetime` (the wide range of section 2.3), `limit: 100` (page size).
        - **Pagination:** the answer contains `context.next`; it is sent back as `body["next"]` to get the next page. The loop is capped at **20 pages** (up to 2000 scenes) so a faulty `next` token cannot loop forever; the catalog for this AOI holds 677 items.
        - **Error messages by status code:** 401 = credentials rejected, 403 = no access / no Monitoring Credits, 404 = try the other deployment in section 2.3. Each hint tells the reader what to change.
        - If nothing is found the cell prints a reminder of the collection's date range and the AOI.
        """),
        c[5],
        md("""
        ## 2.7 Inspect and save the catalog results

        ### 2.7.1 Look at the returned properties
        - The first feature's `properties` are printed as indented JSON (cut at 1500 characters) so you can **see which fields the catalog really offers** before relying on them.
        - Each row keeps the `id`, the `datetime` and **every property whose name contains "cloud"** (`k.lower()` makes the match case-insensitive). The cloud field's exact name is not known in advance, so matching on the word keeps the notebook robust.
        - `results_df["date"] = results_df["datetime"].str[:10]` keeps only `YYYY-MM-DD`, because downloads (section 2.10) are requested **per day**.
        - The cell raises a clear `RuntimeError` if the search returned nothing, then shows the first 30 rows and the sorted list of distinct dates.
        """),
        c[6],
        md("""
        ### 2.7.2 Save the catalog (`all_images_sentinel.csv`)
        One line writes `results_df` to disk without the index. This file is a snapshot of **everything the catalog lists for the AOI (677 items, 2021-01-01 → 2023-12-29)**, i.e. the images that are *available*, whether or not they were downloaded. The Streamlit app reads it to show "images in catalog" next to "images downloaded".
        """),
        c[7],
        md("""
        ## 2.8 Choose a date (single test download)

        ### 2.8.1 Select the date to test with
        - `SELECTED_DATE = None` means "choose for me"; type a date such as `"2022-01-14"` to override.
        - **Automatic rule:** the date with the **lowest mean cloud value**. The mean is taken per date (`groupby("date")`) because a day can contain several scenes. If the catalog carries no cloud field, the earliest date is used.
        - The cell prints which rule was applied and the chosen date, so the choice is traceable.
        A single, low-cloud date is the cheapest way to prove that the download works before spending credits on many dates.
        """),
        c[8],
        md("""
        ## 2.9 Download one GeoTIFF with the Process API (reference version)

        ### 2.9.1 Try the band sets one after the other
        **Important:** the whole cell below is wrapped in a triple-quoted string (`\"\"\" … \"\"\"`). Python therefore reads it as text and **does not execute it**; it is kept as the documented, step-by-step version of the download. The version that actually runs and wrote the files on disk is section 2.10.

        What the reference version does, and why:
        - `CANDIDATE_BANDS` lists three band-name sets: the 4-band surface-reflectance set (`blue, green, red, nir`), the same plus `rededge`, and the 8-band set of the newer PlanetScope generation (`coastal_blue, blue, green_i, green, yellow, red, rededge, nir`). Band names differ by sensor generation, so it **tries the simplest first and falls back**. The first set that succeeds is stored in `used_bands`.
        - `build_evalscript(bands)` writes the small JavaScript program (an **evalscript**) that Sentinel Hub runs per pixel: it requests the chosen bands **plus `dataMask`**, and returns them as `FLOAT32` so reflectance keeps its decimals.
          `dataMask` is added as the **last band** (1 = valid pixel, 0 = no data), which is why the files have 5 bands.
        - `process_request(bands)` builds the request: the `bbox` and its CRS, the collection, a **time range covering only `SELECTED_DATE`** (00:00:00-23:59:59 Z), `mosaickingOrder: "mostRecent"` (if several scenes overlap on that day, the most recent one is on top), the output size from section 2.3 and `image/tiff` as the response format.
        - `timeout=600` (10 min) because rendering a 2400 × 2400 image can take a while.
        - It saves `planet_downloads/ARPS_Para_<date>.tif` (`ARPS` = analysis-ready PlanetScope; `Para` = region). A **401, 403 or 429** stops immediately (credentials, permission or rate limit cannot be fixed by trying another band set); any other error prints the first 600 characters, which usually names the invalid band, and the next set is tried. If all fail, a `RuntimeError` explains what to read.
        - It ends by printing the file path, its size and the band list.
        """),
        c[9],
        md("""
        ## 2.10 Download every 7th date (the production download)

        ### 2.10.1 Select dates, authenticate and download
        This is the cell that creates the per-date GeoTIFFs used by the rest of the workbook. It is written as **one self-contained script** with seven numbered blocks, so it can be run alone after a kernel restart (only `results_df` from section 2.7 is required).

        | Block | What it does | Decision / reason |
        |---|---|---|
        | 1. Settings | Re-declares collection, `BBOX`, `BBOX_CRS`, dates, `BASE_URL`, output folder and `used_bands = ["blue","green","red","nir"]`. | Self-contained on purpose. The 4-band set is the one that worked in section 2.9. `OUTPUT_DIR = Path.cwd() / "planet_downloads"` keeps downloads next to the notebook; `mkdir(parents=True, exist_ok=True)` makes the folder without error if it exists. |
        | 2. Check catalog | Stops with a clear `NameError`/`ValueError` if `results_df` is missing or empty; builds `all_dates`; `picked = all_dates[::STEP]`; always appends the **last** available date. | `STEP = 7`: **take every 7th date** (about one acquisition per week-sample) to cap Processing-Unit use and time while still covering the whole year; the first date is included by the slice, the last is added explicitly so the series always spans the full period. **`STEP` is the one number to change** for a denser or sparser download. |
        | 3. OAuth | Reuses `CLIENT_ID`/`CLIENT_SECRET` from section 2.4 if they exist, otherwise asks with `getpass`; defines `get_access_token()` and `auth_headers()`; tests the login immediately. | Same flow as section 2.5, repeated so the script runs alone. The token is renewed 60 s before expiry; the failure message includes status and the first 500 characters of the answer. |
        | 4. Evalscript | `build_evalscript(bands)` as in section 2.9 (bands + `dataMask`, `FLOAT32`). | Same reasoning: keep decimals, and carry a validity band instead of guessing which pixels are empty. |
        | 5. Request | `process_request(date_string)` for one day with `mosaickingOrder: "mostRecent"`. | One request per day keeps each file a clean snapshot of a single date. |
        | 6. Download loop | Skips existing non-empty files; saves new ones; on 401/403/429 prints why and **stops**; on any other exception stops after printing; `time.sleep(1)` between requests. | **Resumable:** re-running after an interruption continues where it stopped. Stopping on authentication, permission or quota errors avoids burning credits on requests that cannot succeed. The 1 s pause keeps the request rate polite. |
        | 7. Summary | Prints counts, band list, folder and any failed dates. | Lets you see at once whether the run was complete. |

        **Two things to know about this cell**
        - **Image size.** The cell sets `WIDTH = HEIGHT = 1024`, whereas section 2.3 uses 2400 and the files currently on disk are **2400 × 2400** (they were created with the larger size). Set both to 2400 here if you re-download, so that new files match the existing ones and the composites.
        - **Number of files.** `STEP = 7` on the 677-item catalog would give far fewer files than the **317** now in `planet_downloads/` (113 for 2021, 108 for 2022, 96 for 2023). The folder was therefore evidently filled over several runs with a smaller step. The "skip existing files" rule makes that safe.
        """),
        c[10],
        md("""
        ## 2.11 From per-date files to annual composites

        **This step is not contained in any of the three notebooks.** Part 3 loads `composites/composite_2021.tif`, `composite_2022.tif`, `composite_2023.tif` and `composite_All_years.tif` and its error text says "run the composite-generation code once first", but that code is not in the files.
        To document the method honestly, a check was run on the data itself: for a block of pixels, the composite for 2021 was compared with the per-pixel **mean** and the per-pixel **median** of the 113 downloaded 2021 files.
        The median reproduced the composite closely (mean absolute difference ≈ 5 DN, and many composite values end in `.5`, the typical sign of a median over an even number of scenes), the mean did not (≈ 400-585 DN).
        **So the composites are, most likely, per-pixel medians of the per-date files** (an inference: the exact subset of files and the handling of `dataMask` are not recorded).

        **Why a median is a sensible choice here:** clouds, cloud shadows and haze are extreme values in a single date; the median over many dates ignores them without needing a cloud mask. The cost is that the composite mixes the whole year, so seasonal effects are averaged in (see Part 3, section 3.9).

        **Recommendation:** add the composite-generation code to this part (or to a notebook of its own) so that the workbook is reproducible from the raw downloads. It should read `dataMask` (band 5), set invalid pixels to NaN, take `np.nanmedian` per band over the files of each year (and over all files for "All years") and write 4-band float32 GeoTIFFs (blue, green, red, nir) with the same georeferencing.
        """),
        md("""
        ## 2.12 What Part 2 gives to Part 3

        - `all_images_sentinel.csv`: the catalog of every date available over the AOI (677 items).
        - `planet_downloads/ARPS_Para_<date>.tif`: one 5-band float32 GeoTIFF per downloaded date (blue, green, red, nir, dataMask; EPSG:4326; 2400 × 2400 ≈ 10 m).
        - The knowledge that annual composites are built from these files (section 2.11).

        **Limits of Part 2:** the sandbox covers only 2021-2023; per-date files can be mostly empty when the scene covers only part of the AOI (so some files are only partly filled with valid pixels); downloading consumes Processing Units; and the licence is CC-BY-NC.
        """),
    ]
    return nb, cells


# =============================================================================================== PART 3
def part3():
    nb, c = load(2)
    cells = [
        md("""
        # Planet Forest-Change Workflow: Part 3 of 3 · NDVI analysis
        **You are in Part 3 of 3.** Part 2 produced the per-date files and the annual composites; Part 3 reads the four composites (2021, 2022, 2023, All years), calculates **NDVI** and **NDVI change**, classifies decline, counts pixels and finds connected **decline patches**.
        Conventions (numbering, band order, NDVI formula, AOI) are listed at the top of Part 1. *Run this part after restarting the kernel.*
        """),
        md("""
        ## 3.1 Purpose and inputs

        **Question:** between 2021 and 2023, where did green vegetation (forest) become less green, how much area is that, and is it concentrated in a few patches?

        **Inputs:** four 4-band float32 GeoTIFFs in `composites/` (blue, green, red, NIR; EPSG:4326; 2400 × 2400 pixels ≈ 10 m).
        **Outputs:** `composites/ndvi_statistics.csv` and the figures shown in the notebook.

        **Method in one paragraph.** NDVI is computed for each composite; the change is the NDVI of 2023 minus the NDVI of 2021; pixels whose NDVI fell by at least **0.10** (*moderate decline*) or **0.20** (*strong decline*) are counted; the strong-decline mask is cleaned with a morphological opening and closing and split into connected patches; patches of at least **100 pixels (≈ 1 ha)** are reported and outlined.
        """),
        md("""
        ## 3.2 Load the composites

        ### 3.2.1 Read the four GeoTIFFs into memory
        **What the cell below does, and why:**

        - **Libraries:** `pathlib.Path` for paths, `numpy` for arrays, `rasterio` to read GeoTIFFs with their georeferencing, `matplotlib.pyplot` for the figures of the later sections. Imports are repeated in later cells so each can run alone.
        - **`DATA_DIR`** is the (absolute) path of `planet_downloads`, and `OUT_DIR = DATA_DIR.parent / "composites"` is the sibling folder that holds the composites and receives the statistics file. **Change `DATA_DIR` to your own location** when you run the notebook on another computer; everything else is derived from it.
        - `composite_files` lists the four expected files in a fixed order, so every table and figure shows the periods in the same order.
        - `src.read().astype("float32")` loads **all bands** as 32-bit floats (≈ 92 MB per composite): enough precision for ratios and less memory than float64.
        - A **missing file is reported and skipped** (not fatal), but the **All years composite is mandatory**: it is the reference for the contrast stretch in section 3.4, so the cell raises `FileNotFoundError` if it is absent.
        - The printed shapes `(4, 2400, 2400)` and `CRS: EPSG:4326` confirm that all composites are on the same grid, which is what makes pixel-by-pixel comparison valid.
        """),
        c[0],
        md("""
        ## 3.3 Check the data before analysing it

        ### 3.3.1 Print the GeoTIFF information
        `print_geotiff_information(name, path)` prints driver, size, number of bands, CRS, bounds, pixel size, transform, data types, nodata value, the full profile, tags, band descriptions, the share of **valid pixels** and, **per band**, min / max / mean / median / standard deviation.
        **Why:** it is cheaper to spot a wrong CRS, a shifted extent or a band full of zeros here than after three figures.

        - `src.dataset_mask() > 0` uses rasterio's own mask (from nodata or an alpha/mask band) to decide which pixels are valid.
        - Band statistics use only valid, finite values (`np.isfinite`), so NaN/inf cannot distort them.
        - A missing file prints `Status: MISSING` rather than stopping the loop.
        - The configuration block (`DATA_DIR`, `OUT_DIR`, `composite_files`) is repeated so the cell works on its own.
        """),
        c[1],
        md("""
        ### 3.3.2 Test whether a `dataMask` band exists
        The per-date files of Part 2 carry `dataMask` as a 5th band; this cell checks whether the **composites** do too. It reads `src.descriptions` and looks for the name `dataMask`: if found, `image[data_mask_index] > 0` is the valid-pixel mask; if not, it falls back to `src.dataset_mask()`.
        **Note:** the cell uses the variable `path` left over from the previous loop, i.e. it tests the **last** composite (All years) only. The composites contain 4 bands (section 3.2), so the fallback branch is the one that applies.
        """),
        c[2],
        md("""
        ### 3.3.3 Summary table of all composites
        One row per composite with file, status, width, height, bands, CRS, bounding box, pixel size, data type, nodata value and `valid_pixels_percent`. Missing files appear as a row with `status = missing`.
        **Why a table:** four composites should be identical in size, CRS and extent; in one table a difference jumps out. The `file` column holds the full local path (only for your own checking).
        """),
        c[3],
        md("""
        ## 3.4 True-colour view

        ### 3.4.1 Display the four composites as natural-colour images
        **Decisions in the cell below:**

        - **Reference image:** the All-years composite defines the contrast stretch, so every panel is stretched the *same* way. If each panel were stretched separately, differences between years would be hidden or invented.
        - **`STEP = max(1, width // 1200)`**: images are shown at most ≈ 1200 pixels wide by taking every `STEP`-th pixel (here every 2nd). This is **for display only**; all calculations later use the full resolution.
        - **Stretch limits:** the 2nd and 98th percentiles per band (`np.percentile(values, [2, 98])`) ignore extreme dark/bright pixels (cloud, shadow, glint) so the image has good contrast; `values[::10]` subsamples every 10th value so the percentile calculation is fast. A constant band would give `high == low`, so `high = low + 1e-6` avoids a division by zero.
        - **Band order is stated in the code**: in the file, index 0 = blue, 1 = green, 2 = red; `to_rgb` stacks them as **red, green, blue** (`for band_index in (2, 1, 0)`), because screens expect RGB.
        - `np.clip(…, 0, 1)` and `np.nan_to_num` keep every value displayable.
        - `interpolation="nearest"` shows real pixels without smoothing; `origin="upper"` matches how GeoTIFF rows are stored.
        - The four panels are in a **fixed order** (2021, 2022, 2023, All years) on a 2 × 2 grid; a missing composite shows "missing" instead of failing.
        """),
        c[4],
        md("""
        ## 3.5 NDVI

        ### 3.5.1 Calculate NDVI and draw the maps
        NDVI is a ratio, so **it does not depend on whether reflectance is scaled** (the documented ARPS scale is DN/10000): the scale cancels out.

        - **`ndvi_of(arr)`** takes `red = arr[2]` and `nir = arr[3]`: the band order of section 3.2 (blue, green, red, NIR). This is the one place where a wrong band order would silently give a wrong index, so the order is confirmed in the conventions at the top of Part 1.
        - `np.errstate(divide="ignore", invalid="ignore")` silences the warnings when `nir + red = 0` (empty pixels); those pixels become **NaN**, not 0, so empty pixels are never mistaken for "no vegetation".
        - A small table prints **mean, median, 5th and 95th percentile** for each period. The percentiles show spread without being dominated by a few extreme pixels.
        - **NDVI maps:** colour map `RdYlGn` (red = low, green = high) with fixed limits **−0.2 to 1** for every panel. Fixed limits make panels comparable; values below 0 are typically water, cloud or shadow, values above 0.8 dense forest.
        - **Change map 2023 − 2021:** `RdBu` with limits **±0.5**, symmetric around 0 so that white means "no change", red means **loss** and blue means **gain**. The last-year-minus-first-year pair gives the longest time span available.
        - `[::STEP, ::STEP]` again subsamples for display only.
        """),
        c[5],
        md("""
        ### 3.5.2 Print and save the NDVI statistics
        For each composite: number of valid pixels (`len(values)` after removing NaN/inf), mean, median, 5th and 95th percentile, shown rounded to 3 decimals and **saved without rounding** to `composites/ndvi_statistics.csv` (`index=False`).
        Saving the exact numbers means the Streamlit app and any report can reuse them without recomputing.
        In the saved run all composites have **5,759,440 valid pixels** (of 5,760,000) and mean NDVI between 0.806 and 0.810: typical for dense tropical forest, where NDVI saturates near 0.8-0.9.
        """),
        c[6],
        md("""
        ## 3.6 NDVI decline between 2021 and 2023

        ### 3.6.1 Count the pixels that lost vegetation
        - `valid = isfinite(ndvi_2021) & isfinite(ndvi_2023)`: only pixels observed in **both** years are compared.
        - `change[valid] = ndvi_2023 − ndvi_2021` (everything else stays NaN): **negative = decline, positive = increase.**
        - Two thresholds are used: **−0.10** (*moderate or stronger decline*) and **−0.20** (*strong decline*). They are analyst choices: 0.10 is large enough to rise above year-to-year noise; 0.20 is a clear drop (for example NDVI 0.85 → 0.65). The comparison is `<=` so a change of exactly the threshold counts.
        - **Percentages use valid pixels as the denominator**, so unobserved pixels cannot make the loss look smaller.
        - Saved result: **307,956 pixels (5.35 %)** declined by ≥ 0.10 and **44,290 pixels (0.77 %)** by ≥ 0.20.
        """),
        c[7],
        md("""
        ### 3.6.2 Map the decline
        The explanation of this section, kept from the original notebook: the code compares NDVI from 2021 and 2023 to identify areas where vegetation declined and creates **two maps** - the left shows pixels with NDVI decline of at least **0.10**, the right those with at least **0.20**.

        **Decisions in the cell below:**
        - It recalculates `valid_2021`, `valid_2023` and the change itself, so it works alone, and **checks that both arrays have the same shape** (raises `ValueError` otherwise): comparing shifted grids would give meaningless results.
        - `valid_change` restricts every count to pixels valid in both years; a `ValueError` stops the cell if there are none (a division by zero would otherwise follow).
        - Counts and percentages are computed once and **reused in the map titles**, so the figure and the printed numbers can never disagree.
        - The maps are **binary** (`Reds`, `vmin=0`, `vmax=1`): a pixel either passed the threshold or not. `DISPLAY_STEP` subsamples for display only.
        """),
        c[8],
        md("""
        ## 3.7 Decline patches

        ### 3.7.1 Clean the mask and label connected patches
        A raw threshold mask contains isolated specks and tiny gaps that are noise rather than real forest loss; the cell turns the strong-decline mask into **patches**.

        - **Opening, then closing, with a 3 × 3 structure** (`np.ones((3, 3))`): *opening* (erode, then dilate) removes specks smaller than 3 × 3 pixels; *closing* (dilate, then erode) fills 1-pixel holes so one clearing is not split into fragments. Doing the opening first avoids filling the gaps between noise specks.
        - **`ndimage.label`** gives each connected group of pixels its own number. With no structure argument it uses **4-connectivity** (pixels must share an edge). The Streamlit app uses 8-connectivity (corners count too), which is why it reports 310 candidate patches against 311 here: a small, expected difference.
        - `np.bincount(labels.ravel())[1:]` counts the pixels per patch (the `[1:]` drops label 0, the background).
        - **100 pixels** is the minimum patch size: at ≈ 10 m × 10 m per pixel this is **≈ 1 hectare**, a common lower bound for mapping forest loss and large enough to be visible and checkable in the field.
        - Saved result: **311 decline patches, 55 with at least 100 pixels, the largest 2,433 pixels (≈ 24 ha)**.
        """),
        c[9],
        md("""
        ### 3.7.2 Outline the large patches
        **What the boxes mean** (original notebook explanation, kept): each yellow rectangle is the **smallest rectangle containing one connected patch**; the red area is the cleaned decline mask; every rectangle surrounds a patch of at least 100 pixels; the white number is the patch ID and size. The rectangles may contain pixels that are not part of the patch, because they are *bounding boxes*, not exact outlines. `ndimage.find_objects()` returns these slices. If 55 rectangles are too many, show only the 10 largest.

        **Decisions in the cell below:** `find_objects(labels)` returns one slice pair per label, so `objects[patch_id - 1]` is the box of patch `patch_id`; a `None` slice is skipped; `Rectangle` outlines (`fill=False`, yellow, 1.5 pt) and a small black-backed label show ID and pixel count without hiding the map.

        > **Known issue (the code is intentionally unchanged):** this cell uses two names that are not defined in the saved notebook, `large_patch_ids` (the list of patch IDs with ≥ 100 pixels) and `Rectangle` (from `matplotlib.patches`). The saved output is a `NameError`, and its low execution number shows it was last run in an earlier session. To make it run, add these two lines in a cell before it:
        > `from matplotlib.patches import Rectangle`
        > `large_patch_ids = np.flatnonzero(patch_sizes >= 100) + 1`
        """),
        c[10],
        md("""
        ### 3.7.3 Spare cell
        The empty code cell below is left in place; it can be used for further experiments or be deleted.
        """),
        c[11],
        md("""
        ## 3.8 Interpretation

        The NDVI change map identifies locations where vegetation conditions differed between the selected periods. Areas with negative change may indicate vegetation loss, but they may also result from seasonality, cloud contamination, fire, drought, flooding, harvest, or different acquisition dates. Results should therefore be interpreted as **areas for investigation rather than confirmed deforestation**.

        **What the numbers say:** mean NDVI is almost unchanged (0.810 → 0.807); about **5.35 %** of the valid area lost at least 0.10 NDVI and **0.77 %** at least 0.20 (≈ 437 ha of the 568 km²). The strong decline is concentrated in **55 patches of ≥ 1 ha**, so the change is spatially concentrated rather than spread evenly.
        """),
        md("""
        ## 3.9 Limitations

        - NDVI change is an indicator for investigation, not definitive proof of deforestation; the cause of a change is not identified.
        - **Seasonality.** The compared scenes or annual composites may represent different seasons. A difference in NDVI may therefore reflect rainfall and seasonal vegetation dynamics rather than permanent land-cover change. For stronger conclusions, compare images from similar months, use multiple observations per year, and apply cloud and quality masks consistently.
        - Each annual composite is built from a different set of acquisitions (113, 108 and 96 files), so atmospheric, phenological and radiometric differences can leak into the change.
        - The composite step is not part of the notebooks (section 2.11), so the exact method is inferred, not documented.
        - Three annual points give a trajectory classification, not a statistically established trend.
        - Thresholds (0.10 and 0.20) and the 100-pixel minimum are analyst choices; the reported area moves with them. The Streamlit app limits the thresholds to 0.10-0.20 and shows a sensitivity chart.
        - Pixel counts are not areas: the pixel size changes slightly with latitude (the app weights each row by its true area).
        - The sandbox data are licensed CC-BY-NC and cover 2021-01-01 to 2023-12-29.
        - Dense forest saturates NDVI near 0.8-0.9, so NDVI is insensitive to changes within closed forest (degradation) and best at detecting clearing.
        """),
        md("""
        ## 3.10 Future scope

        - Compare images from the same months or seasons.
        - Use monthly or quarterly time series instead of only annual composites.
        - Add rainfall, soil-moisture or soil-condition, temperature and drought indicators.
        - Add fire and burn-scar data; add true-colour and false-colour composites.
        - Add indices related to water, burn severity or vegetation stress.
        - Add land-cover and protected-area layers; compare results with official deforestation datasets (PRODES, DETER, MapBiomas).
        - Add automated alerts for new change patches and confidence scores.
        - Add field observations or validation points.
        - Add cloud-probability and image-quality reporting.
        - Add user-uploaded areas of interest; authenticated Planet API processing; scheduled data updates; historical time-series charts; automated PDF report generation.
        - Add a model to distinguish likely deforestation from seasonal or atmospheric effects.
        - Add the composite-generation code to the workbook (section 2.11) and fix the patch-outline cell (section 3.7.2).

        *Each of these would require additional data, validation and processing time.*
        """),
    ]
    return nb, cells


for i, builder in enumerate((part1, part2, part3)):
    nb, cells = builder()
    nb["cells"] = cells
    nb.setdefault("metadata", {})
    out = ROOT / FILES[i]
    with open(out, "w") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    n_code = sum(c["cell_type"] == "code" for c in cells)
    print(out.name, "cells:", len(cells), "code:", n_code)
