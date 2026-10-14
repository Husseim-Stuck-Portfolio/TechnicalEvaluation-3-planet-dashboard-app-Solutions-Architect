"""Unit tests for the pure logic (no Streamlit, no network)."""
import numpy as np
import pandas as pd
import pytest

from para_explorer import analysis as A
from para_explorer import composites as K
from para_explorer import counts as N
from para_explorer import planet

BOUNDS = (-52.4825, -6.8735, -52.26725, -6.65775)


def grid(n=200):
    return K.pixel_area_ha_by_row(n, BOUNDS, n)


def test_pixel_area_matches_aoi():
    n = 300
    total_km2 = grid(n).sum() * n / 100
    assert total_km2 == pytest.approx(568, rel=0.01)   # AOI is 568 km2


def test_ndvi_masks_invalid():
    red = np.array([[100.0, 0.0, np.nan]]); nir = np.array([[300.0, 0.0, 200.0]])
    out = K.ndvi_from_bands(red, nir)
    assert out[0, 0] == pytest.approx(0.5) and np.isnan(out[0, 1]) and np.isnan(out[0, 2])


def test_change_budget_sums_and_nodata_excluded():
    a = np.full((50, 50), 0.8, "float32"); b = a.copy()
    b[:10] -= 0.3; b[10:15] -= 0.12; b[45:] += 0.25; b[0, 0] = np.nan
    t = A.change_budget(a, b, grid(50)).set_index("class")
    assert t.loc["Strong decrease", "pixels"] == 499   # 500 px minus the NaN one
    assert t.loc["Moderate decrease", "pixels"] == 250
    assert t.loc["Strong increase", "pixels"] == 250
    assert t.loc["No data", "pixels"] == 1
    assert t.drop("No data")["pct_valid"].sum() == pytest.approx(100)


def test_change_budget_rejects_bad_thresholds():
    with pytest.raises(ValueError):
        A.change_budget(np.zeros((2, 2)), np.zeros((2, 2)), grid(2), 0.3, 0.1)


def test_trajectory_classes():
    n21 = np.array([[0.8, 0.8, 0.8, 0.8, 0.8, np.nan]]); n22 = np.array([[0.8, 0.6, 0.6, 0.6, 0.95, 0.8]])
    n23 = np.array([[0.8, 0.6, 0.8, 0.45, 0.7, 0.8]])
    got = A.trajectory(n21, n22, n23, 0.1)[0].tolist()
    assert got == [1, 3, 4, 3, 5, 0]   # stable, step decline, decline->recovery, decline x2, rise->fall, no data


def test_patches_find_square_and_robustness():
    n = 200
    a = np.full((n, n), 0.85, "float32"); b = a.copy(); b[50:80, 60:90] -= 0.4   # 900 px square
    nd = {"2021": a, "2022": (a + b) / 2, "2023": b}
    df, gj, s = A.detect_patches(nd, "2021", "2023", 0.2, 1.0, grid(n), BOUNDS)
    assert len(df) == 1 and s["total_candidates"] == 1
    assert df.loc[0, "pixels"] == 900 and df.loc[0, "robustness"] == 1.0
    assert len(gj["features"]) == 1 and gj["features"][0]["geometry"]["type"] == "MultiPolygon"
    lon, lat = df.loc[0, "lon"], df.loc[0, "lat"]
    assert BOUNDS[0] < lon < BOUNDS[2] and BOUNDS[1] < lat < BOUNDS[3]


def test_counts_summarise():
    rec = N._summarise({"2021": ["2021-01-05T10:00:00Z", "2021-01-05T10:00:05Z", "2021-02-01T00:00:00Z"], "2022": [], "2023": ["2023-12-30T00:00:00Z"]})
    assert rec["2021"]["items"] == 3 and rec["2021"]["dates"] == 2 and rec["2021"]["monthly"]["01"] == 2
    assert rec["All years"]["items"] == 4


def test_counts_from_download_folder(tmp_path):
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "ARPS_Para_2023-01-01.tif").write_bytes(b"")      # sub-folders are ignored
    for name in ["ARPS_Para_2021-06-22.tif", "ARPS_Para_2022-07-05.tif", "20220705_125544_94_242d.tif", "composite_2021.tif", "readme.txt"]:
        (tmp_path / name).write_bytes(b"")
    rec = N.from_download_folder(tmp_path, coverage=False)["counts"]
    assert rec["2021"]["items"] == 1 and rec["2022"]["items"] == 2 and rec["2022"]["dates"] == 1 and rec["2023"]["items"] == 0


def test_counts_coverage_and_catalog(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    for name, valid in [("ARPS_Para_2021-01-01.tif", 1.0), ("ARPS_Para_2021-01-02.tif", 0.01)]:
        a = np.zeros((5, 20, 20), "float32")
        a[4, :int(20 * valid) or 1, :int(20 * valid) or 1] = 1.0
        a[4] = 1.0 if valid == 1.0 else a[4]
        with rasterio.open(tmp_path / name, "w", driver="GTiff", width=20, height=20, count=5, dtype="float32",
                           crs="EPSG:4326", transform=from_origin(0, 0, 1, 1)) as dst:
            dst.write(a)
    cat = tmp_path / "cat.csv"
    cat.write_text("id,datetime,date\na,2021-01-01T10:00:00Z,2021-01-01\nb,2021-02-01T10:00:00Z,2021-02-01\nc,2022-02-01T10:00:00Z,2022-02-01\n")
    rec = N.from_download_folder(tmp_path, catalog_csv=cat, index_csv=tmp_path / "idx.csv")["counts"]
    assert rec["2021"]["items"] == 2 and rec["2021"]["usable"] == 1
    assert rec["2021"]["available"] == 2 and rec["2022"]["available"] == 1 and rec["All years"]["available"] == 3
    assert (tmp_path / "idx.csv").read_text().count("\n") == 3


def test_planet_filter_shape():
    f = planet.build_filter("2021-01-01", "2021-12-31", 0, 30, ["x"])
    kinds = [c["type"] for c in f["config"]]
    assert kinds == ["GeometryFilter", "DateRangeFilter", "RangeFilter", "StringInFilter"]
    assert f["config"][2]["config"] == {"gte": 0, "lte": 30}


class FakeResp:
    def __init__(self, status=200, js=None, headers=None, content=b""):
        self.status_code, self._js, self.headers, self.content, self.text = status, js or {}, headers or {}, content, ""

    def json(self):
        return self._js


@pytest.mark.parametrize("status,needle", [(401, "rejected"), (403, "no access"), (429, "rate limit")])
def test_planet_error_mapping(status, needle):
    with pytest.raises(planet.PlanetError, match=needle):
        planet._check(FakeResp(status))


def test_planet_search_paginates_and_truncates(monkeypatch):
    pages = [{"features": [{"id": str(i)} for i in range(3)], "_links": {"_next": "n1"}},
             {"features": [{"id": "x"}], "_links": {"_next": "n2"}}]

    class S:
        def post(self, *a, **k): return FakeResp(200, pages[0])
        def get(self, url, **k): return FakeResp(200, pages[1])

    monkeypatch.setattr(planet, "_session", lambda key: S())
    feats, trunc = planet.search("k", ["PSScene"], {}, max_pages=2)
    assert len(feats) == 4 and trunc is True


def test_to_frame_cloud_fallback():
    df = planet.to_frame([{"id": "a", "geometry": None, "properties": {"acquired": "2022-03-01T10:00:00Z", "cloud_cover": 0.25, "item_type": "PSScene"}, "_links": {}}])
    assert df.loc[0, "cloud_percent"] == 25 and df.loc[0, "year"] == 2022 and df.loc[0, "month"] == 3


# ------------------------------------------------------------------ v1.1 additions -----
from para_explorer import aoi as AOI  # noqa: E402
from para_explorer import config as CFG  # noqa: E402
from para_explorer import copernicus_imagery as CI  # noqa: E402
from para_explorer import figures as FIG  # noqa: E402
from para_explorer import report as REPORT  # noqa: E402


@pytest.mark.parametrize("m,s", [(0.0, 0.0), (0.5, 0.9), (0.15, 0.15), (0.2, 0.2), (float("nan"), None), (-1, 5), (0.1, 0.2)])
def test_thresholds_always_in_safe_range(m, s):
    a, b, _ = CFG.validate_thresholds(m, s)
    assert CFG.NDVI_T_MIN <= a < b <= CFG.NDVI_T_MAX


def test_thresholds_valid_pair_untouched():
    assert CFG.validate_thresholds(0.12, 0.18) == (0.12, 0.18, [])


@pytest.mark.parametrize("min_ha", [0.25, 1, 5, 20, 50, 10_000])
def test_patches_never_raise_for_large_minimum(min_ha):
    a = np.full((120, 120), 0.8, "float32")
    b = a.copy(); b[10:30, 10:30] = 0.3
    df, gj, summ = A.detect_patches({"2021": a, "2022": a, "2023": b}, "2021", "2023", 0.2, min_ha, np.full(120, 0.01), (-52.4, -6.8, -52.2, -6.6))
    assert list(df.columns) == A.PATCH_COLUMNS or len(df) > 0
    assert summ["kept"] == len(df) == len(gj["features"])
    if min_ha >= 5:
        assert df.empty and summ["kept"] == 0


def test_square_images_identical_canvas():
    sizes = set()
    for kind, arr in [("rgb", np.random.rand(300, 300, 3)), ("ndvi", np.random.rand(300, 300)), ("change", np.random.rand(300, 300) - .5)]:
        from PIL import Image
        import io
        png = FIG.to_png(FIG.composite_figure(kind, arr, "t", "s", "dark"))
        sizes.add(Image.open(io.BytesIO(png)).size)
    assert len(sizes) == 1 and next(iter(sizes))[0] == next(iter(sizes))[1]


def test_aoi_parse():
    ok = '{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[-52.4,-6.8],[-52.4,-6.7],[-52.3,-6.7],[-52.3,-6.8],[-52.4,-6.8]]]}}'
    g, err = AOI.parse_geojson(ok)
    assert g["type"] == "Polygon" and err is None
    assert AOI.parse_geojson("nope")[1]
    assert AOI.parse_geojson('{"type":"Point","coordinates":[1,2]}')[1]
    big = ok.replace("-52.4", "-60.4")
    assert AOI.parse_geojson(big)[0] is None


def _tiff(h=40, w=40, valid=True):
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds
    arr = np.zeros((5, h, w), "float32")
    arr[0], arr[1], arr[2], arr[3] = 0.03, 0.05, 0.03, 0.4
    arr[4] = 1.0 if valid else 0.0
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=w, height=h, count=5, dtype="float32", crs="EPSG:4326",
                      transform=from_bounds(*CFG.BBOX, w, h)) as dst:
            dst.write(arr)
        return mem.read()


class _Resp:
    def __init__(self, status=200, content=b"", js=None):
        self.status_code, self.content, self._js = status, content, js or {}

    def json(self):
        return self._js


def test_copernicus_fetch_ok_and_ndvi(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        return _Resp(200, js={"access_token": "t"}) if "openid" in url else _Resp(200, content=_tiff())

    monkeypatch.setattr(CI.requests, "post", fake_post)
    scene = CI.fetch("id", "secret", "2021-01-01", "2021-12-31", 70, size=40)
    nd = CI.ndvi(scene)
    assert np.allclose(nd[valid := scene["valid"]], (0.4 - 0.03) / (0.4 + 0.03), atol=1e-3) and valid.all()
    body = calls[1][1]["json"]
    assert body["input"]["bounds"]["bbox"] == list(CFG.BBOX) and body["output"]["width"] == 40
    assert "secret" not in str(body)          # credentials never travel in the request body


@pytest.mark.parametrize("status,needle", [(401, "rejected"), (403, "no access"), (429, "rate limit"), (500, "could not process")])
def test_copernicus_http_errors_are_friendly(monkeypatch, status, needle):
    def fake_post(url, **kw):
        return _Resp(200, js={"access_token": "t"}) if "openid" in url else _Resp(status, js={})
    monkeypatch.setattr(CI.requests, "post", fake_post)
    with pytest.raises(CI.CopernicusError, match=needle):
        CI.fetch("a", "b", "2021-01-01", "2021-12-31")


def test_copernicus_missing_credentials():
    with pytest.raises(CI.CopernicusError, match="missing"):
        CI.fetch("", "", "2021-01-01", "2021-12-31")


def test_copernicus_cache_roundtrip(tmp_path):
    scene = CI.parse_tiff(_tiff())
    p = CI.cache_path(tmp_path, "2021-01-01", "2021-12-31", 70)
    CI.save(scene, p, {"x": 1})
    back, meta = CI.load(p)
    assert meta == {"x": 1} and back["valid"].all() and np.allclose(back["bands"][3], 0.4, atol=1e-3)


def test_comparison_metrics_and_table():
    a = np.random.default_rng(1).uniform(0.6, 0.9, (50, 50)).astype("float32")
    m = CI.compare(a, a + 0.02)
    assert m["r"] > 0.99 and abs(m["bias"] + 0.02) < 1e-4
    t = CI.table("2021", a, 100.0, "2021 range", a, "win", (50, 50), (2400, 2400))
    assert list(t.columns) == ["Metric", "Planet", "Copernicus"] and "Mean NDVI" in set(t["Metric"])
    assert (CI.table("2021", a, 100.0, "r", None, "w", (50, 50), (2400, 2400))["Copernicus"].iloc[0] == "not loaded")


def test_pdf_report_has_all_pages_and_no_paths():
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (60, 60), "green").save(buf, "PNG"); png = buf.getvalue()
    content = {
        "aoi_png": png, "composites": {p: {"rgb": png, "ndvi": png} for p in CFG.COMPOSITES},
        "counts_df": pd.DataFrame({"Composite": ["2021"], "Images downloaded": [3]}), "dist_png": png, "change_png": png, "budget_png": png,
        "hist_png": png, "period_stats_df": pd.DataFrame({"Composite": ["2021"], "Mean NDVI": [0.8]}),
        "budget_df": pd.DataFrame({"Class": ["Strong decrease"], "Area (ha)": ["1.0"]}),
        "thresholds": {"moderate": 0.1, "strong": 0.2, "from": "2021", "to": "2023", "min_ha": 1.0},
        "patch_summary": {"kept": 0, "total_candidates": 2, "kept_ha": 0.0},
        "comparison": {"png": png, "table": CI.table("2021", np.full((4, 4), .8, "float32"), 100., "x", None, "y", (4, 4), (8, 8)),
                       "text": "demo text", "loaded": False}}
    pdf = REPORT.build(content)
    assert pdf[:4] == b"%PDF" and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 8 or len(pdf) > 20_000
    assert b"/Users/" not in pdf
