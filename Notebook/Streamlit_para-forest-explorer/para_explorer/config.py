"""Central configuration: area of interest, composite definitions, endpoints.

Everything that is a *constant of the use case* lives here so that the rest of the
code base stays free of magic numbers and the AOI can be swapped in one place.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"   # real outputs of `python -m para_explorer.precompute`

# The app lives in  <Notebook>/Streamlit_para-forest-explorer ; the notebooks write their data one level up.
# Every location can be overridden with an environment variable.
NOTEBOOK_DIR = Path(os.environ.get("PARA_NOTEBOOK_DIR", ROOT.parent))
RAW_COMPOSITES_DIR = Path(os.environ.get("PARA_COMPOSITES_DIR", NOTEBOOK_DIR / "composites"))   # composite_*.tif (notebook 3)
DOWNLOADS_DIR = Path(os.environ.get("PARA_DOWNLOADS_DIR", NOTEBOOK_DIR / "planet_downloads"))   # ARPS_Para_<date>.tif (notebook 2)
CATALOG_CSV = Path(os.environ.get("PARA_CATALOG_CSV", NOTEBOOK_DIR / "all_images_sentinel.csv"))  # catalog search result (notebook 2)
PLANET_SCENES_CSV = Path(os.environ.get("PARA_SCENES_CSV", NOTEBOOK_DIR / "all_images_values.csv"))  # Planet Data API scenes (notebook 1)

# --------------------------------------------------------------------------- #
# Area of interest (GeoJSON exported from the Copernicus Data Space Ecosystem browser)
# --------------------------------------------------------------------------- #
AOI_FEATURE: dict = {
    "id": "0",
    "type": "Feature",
    "properties": {
        "from": "2015-01-01",
        "to": "2017-01-01",
        "center_x": -52.37487500000001,
        "center_y": -6.765613263405268,
        "area_sqkm": 568.0,
        "collection_id": "f3312c82-edea-42a1-8c9d-ada86ddcc857",
        "geolocation": "Pará, North Region, Brazil",
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [-52.4825, -6.8735],
            [-52.4825, -6.65775],
            [-52.26725, -6.65775],
            [-52.26725, -6.8735],
            [-52.4825, -6.8735],
        ]],
    },
}
AOI_GEOMETRY: dict = AOI_FEATURE["geometry"]
AOI_NAME = AOI_FEATURE["properties"]["geolocation"]
AOI_AREA_KM2 = AOI_FEATURE["properties"]["area_sqkm"]

_ring = AOI_GEOMETRY["coordinates"][0]
_lons = [p[0] for p in _ring]
_lats = [p[1] for p in _ring]
#: (west, south, east, north) in EPSG:4326
BBOX: tuple[float, float, float, float] = (min(_lons), min(_lats), max(_lons), max(_lats))
CENTER_LON = AOI_FEATURE["properties"]["center_x"]
CENTER_LAT = AOI_FEATURE["properties"]["center_y"]

# --------------------------------------------------------------------------- #
# Composites (from notebook 3: 4-band float32 GeoTIFFs, band order B, G, R, NIR)
# --------------------------------------------------------------------------- #
COMPOSITES: tuple[str, ...] = ("2021", "2022", "2023", "All years")
YEARS: tuple[str, ...] = ("2021", "2022", "2023")
BAND_ORDER = ("blue", "green", "red", "nir")  # index 0..3 in the GeoTIFFs

#: Time window each composite covers (the sandbox collection ends on 2023-12-29).
COMPOSITE_WINDOWS: dict[str, tuple[str, str]] = {
    "2021": ("2021-01-01", "2021-12-31"),
    "2022": ("2022-01-01", "2022-12-31"),
    "2023": ("2023-01-01", "2023-12-31"),
    "All years": ("2021-01-01", "2023-12-31"),
}


def slug(name: str) -> str:
    """'All years' -> 'all_years' (file-name safe)."""
    return name.strip().lower().replace(" ", "_")


# --------------------------------------------------------------------------- #
# Sentinel Hub (hosts the Planet *sandbox* BYOC collection) - OAuth client credentials
# --------------------------------------------------------------------------- #
SH_COLLECTION = "byoc-3f605f75-86c4-411a-b4ae-01c896f0e54e"  # PS_ARD_SR_DAILY sandbox
SH_TOKEN_URL = "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
SH_CATALOG_URL = "https://services.sentinel-hub.com/api/v1/catalog/1.0.0/search"

# --------------------------------------------------------------------------- #
# Planet Data API (api.planet.com) - API-key (basic auth) workflow of notebook 1
# --------------------------------------------------------------------------- #
PLANET_DATA_URL = "https://api.planet.com/data/v1"
PLANET_DEFAULT_ITEM_TYPES = ("PSScene",)
PLANET_ALL_ITEM_TYPES = ("PSScene", "SkySatCollect", "PelicanScene")

# --------------------------------------------------------------------------- #
# Copernicus Data Space Ecosystem (public STAC, no credentials needed for search)
# --------------------------------------------------------------------------- #
CDSE_STAC_URL = "https://stac.dataspace.copernicus.eu/v1"
CDSE_S2_COLLECTION = "sentinel-2-l2a"

# --------------------------------------------------------------------------- #
# INPE TerraBrasilis (PRODES) - optional external evidence (idea 9)
# --------------------------------------------------------------------------- #
PRODES_WFS_URL = "https://terrabrasilis.dpi.inpe.br/geoserver/ows"
PRODES_LAYER = "prodes-legal-amz:yearly_deforestation"

# Scene IDs from notebook 1 ("requested" curated scenes, 2016-2026)
CURATED_SCENE_IDS: list[str] = [
    "20160816_125717_0e0d", "20160816_125718_0e0d", "20160816_125719_0e0d", "20160816_125816_0e0f",
    "20160816_125817_0e3a", "20160816_125817_0e0f", "20160816_125818_0e0f", "20160816_125819_0e3a",
    "20160816_125819_0e0f", "20160816_125820_0e3a", "20160816_125821_0e0f", "20160816_125821_0e3a",
    "20160816_125828_0e16", "20160816_125829_0e16", "20160816_125831_0e16", "20160816_125832_0e16",
    "20170622_130057_1026", "20170622_130058_1026", "20170622_130100_1026", "20170622_130101_1026",
    "20170622_130102_1026", "20170622_130148_1024", "20170622_130149_1024", "20170622_130151_1024",
    "20170622_130152_1024", "20170622_130153_1024", "20200709_131451_0e19", "20200709_131452_0e19",
    "20200709_131453_0e19", "20200709_131454_0e19", "20200709_131455_0e19", "20200709_134256_01_105c",
    "20200709_134257_89_105c", "20200709_134259_76_105c", "20210622_130016_76_2440",
    "20210622_130019_06_2440", "20210622_130021_37_2440", "20210622_130136_01_2429",
    "20210622_130138_31_2429", "20210622_135008_90_2419", "20210622_135011_38_2419",
    "20210622_135013_86_2419", "20220705_125542_65_242d", "20220705_125544_94_242d",
    "20220705_125547_24_242d", "20220705_132656_22_2482", "20220705_132658_50_2482",
    "20220705_132700_78_2482", "20230625_133059_08_2438", "20230625_133101_19_2438",
    "20230625_133103_30_2438", "20230625_133150_27_2495", "20230625_133152_41_2495",
    "20230625_133154_55_2495", "20240729_135811_12_24f5", "20240729_135813_35_24f5",
    "20240729_135815_59_24f5", "20240729_135949_11_24e0", "20240729_135951_35_24e0",
    "20240729_135953_59_24e0", "20250721_141153_79_251c", "20250721_141156_03_251c",
    "20250721_141640_52_252e", "20250721_141642_63_252e", "20250721_141644_73_252e",
    "20260802_135033_78_254d", "20260802_135035_88_254d", "20260802_135037_98_254d",
    "20260802_142722_38_253d", "20260802_142724_35_253d", "20260802_142726_32_253d",
    "20260802_143448_16_2409", "20260802_143449_97_2409", "20260802_143451_78_2409",
    "20260802_143617_56_24db", "20260802_143621_57_24db",
]

# --------------------------------------------------------------------------- #
# Analysis defaults (all exposed as widgets in the app)
# --------------------------------------------------------------------------- #
DEFAULT_T_MODERATE = 0.10   # NDVI change counted as "moderate"  (notebook: 0.10)
DEFAULT_T_STRONG = 0.20     # NDVI change counted as "strong"    (notebook: 0.20)
DEFAULT_MIN_PATCH_HA = 1.0  # ~100 px at the native 10 m grid (notebook: >=100 px)
SENS_THRESHOLDS = (0.10, 0.15, 0.20, 0.25, 0.30)
SENS_MIN_HA = (0.25, 0.5, 1.0, 2.0)
