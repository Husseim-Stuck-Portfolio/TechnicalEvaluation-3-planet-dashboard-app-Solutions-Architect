"""Offline tests for notebooks 1 and 2: run their code cells with the network replaced by fakes.

usage: python test_nb12.py <folder with the notebooks>
"""
import getpass as gp, io, json, os, sys, tempfile, types
from pathlib import Path

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

folder = Path(sys.argv[1])
work = Path(tempfile.mkdtemp())
os.chdir(work)


def cells(name):
    nb = json.load(open(folder / name))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


# ---- fakes ---------------------------------------------------------------------------------------------
shown = []
ipy = types.ModuleType("IPython"); disp = types.ModuleType("IPython.display")
disp.display = lambda obj: shown.append(obj)
disp.Markdown = lambda t: ("md", t)
disp.Image = lambda data, width=None: ("img", len(data))
sys.modules["IPython"], sys.modules["IPython.display"] = ipy, disp
answers = iter([])
gp.getpass = lambda prompt="": next(answers)

import requests, time
time.sleep = lambda s: None


class Resp:
    def __init__(self, status=200, js=None, content=b"", text=""):
        self.status_code, self._js, self.content, self.text = status, js, content, text
        self.ok = status < 400
    def json(self): return self._js
    def raise_for_status(self):
        if not self.ok: raise requests.HTTPError(str(self.status_code))


def run(src_cells, ns, skip=()):
    for i, src in enumerate(src_cells):
        if i in skip:
            continue
        exec(compile(src, f"<cell {i}>", "exec"), ns)


# ================================================================ notebook 1
c1 = cells("1_Planet_API_imagery_discovery.ipynb")
ns1 = {"__name__": "__main__"}
answers = iter(["FAKE-KEY"])
exec(c1[0], ns1)            # authenticate
exec(c1[1], ns1)            # AOI
ids = None
exec(c1[2].split("query = ")[0], ns1)
ids = ns1["REQUESTED_SCENE_IDS"]
assert len(ids) == 76 and len(set(ids)) == 76, (len(ids), len(set(ids)))


def post1(url, json=None, auth=None, timeout=None, **kw):
    assert url.endswith("quick-search") and auth == ("FAKE-KEY", "") and timeout == (15, 60)
    cfg = json["filter"]["config"]
    assert cfg[0]["type"] == "GeometryFilter" and cfg[1]["config"] == ids
    feats = [{"id": i, "properties": {"acquired": f"{i[:4]}-{i[4:6]}-{i[6:8]}T{i[9:11]}:{i[11:13]}:{i[13:15]}Z",
                                     "cloud_percent": 5 * k, "quality_category": "standard", "item_type": "PSScene"},
              "_links": {"thumbnail": f"https://x/{i}/thumb", "_self": f"https://x/{i}", "assets": f"https://x/{i}/a"},
              "_permissions": ["assets:download"]} for k, i in enumerate(ids[:12])]
    feats.append({"id": ids[12], "properties": {}, "_links": {}})          # no time, no thumbnail
    return Resp(200, {"features": feats})


requests.post = post1
requests.get = lambda url, auth=None, timeout=None, **kw: Resp(200, content=b"\x89PNG-fake")
for src in c1[2:]:
    exec(src, ns1)
import pandas as pd
saved = pd.read_csv("all_images_values.csv")
assert list(saved.columns) == ["id", "acquired", "cloud_percent", "quality_category"] and len(saved) == 13, saved.shape
assert sum(1 for s in shown if isinstance(s, tuple) and s[0] == "img") == 12
print("notebook 1 OK: 13 rows saved, 12 previews shown, unavailable one reported")

# 401 path
requests.post = lambda *a, **k: Resp(401)
try:
    exec(c1[2], ns1)
    raise SystemExit("401 not raised")
except PermissionError:
    print("notebook 1 OK: HTTP 401 -> PermissionError")

# ================================================================ notebook 2
c2 = cells("2_planet_sandbox_Para_BRA_sentinelhub.ipynb")
ns2 = {"__name__": "__main__"}
exec(c2[0], ns2)                                  # setup
exec(c2[1], ns2)                                  # settings
SIZE = 48
ns2["WIDTH"] = ns2["HEIGHT"] = SIZE
answers = iter(["client-id", "client-secret"])
exec(c2[2], ns2)                                  # credentials
dates = [f"{y}-{m:02d}-{d:02d}" for y in (2021, 2022, 2023) for m in range(1, 13) for d in (3, 17)]
calls = {"token": 0, "catalog": 0, "process": []}


def make_tif(date, width, height):
    rng = np.random.default_rng(int(date.replace("-", "")))
    data = rng.uniform(500, 4000, (5, height, width)).astype("float32")
    data[4] = 1
    if date.endswith("17"):                       # partial footprint: left half empty
        data[:4, :, : width // 2] = 0
        data[4, :, : width // 2] = 0
    if date == "2022-04-03":                      # almost empty date: must be excluded by MIN_COVERAGE
        data[4] = 0
        data[4, :2, :2] = 1
    prof = dict(driver="GTiff", dtype="float32", count=5, width=width, height=height, crs="EPSG:4326",
                transform=from_origin(-52.48, -6.65, 1e-3, 1e-3))
    with MemoryFile() as mem:
        with mem.open(**prof) as dst:
            dst.write(data)
        return mem.read()


def post2(url, headers=None, json=None, data=None, timeout=None, **kw):
    if "openid-connect/token" in url:
        calls["token"] += 1
        assert data["client_id"] == "client-id" and data["grant_type"] == "client_credentials"
        return Resp(200, {"access_token": "T", "expires_in": 3600})
    assert headers["Authorization"] == "Bearer T"
    if url.endswith("/catalog/1.0.0/search"):
        calls["catalog"] += 1
        if calls["catalog"] == 1:
            return Resp(404, text="nope")          # first path 404 -> second path is tried
    if "catalog" in url:
        page = 2 if json.get("next") else 1
        feats = [{"id": f"S{d}", "properties": {"datetime": f"{d}T14:00:00Z", "eo:cloud_cover": 1.0}}
                 for d in (dates[:36] if page == 1 else dates[36:])]
        return Resp(200, {"features": feats, "context": {"next": 36 if page == 1 else None}})
    if url.endswith("/process"):
        d = json["input"]["data"][0]["dataFilter"]["timeRange"]["from"][:10]
        o = json["output"]
        assert headers["Accept"] == "image/tiff" and '"dataMask"' in json["evalscript"]
        calls["process"].append(d)
        return Resp(200, content=make_tif(d, o["width"], o["height"]))
    raise AssertionError(url)


requests.post = post2
exec(c2[3], ns2)                                  # token
exec(c2[4], ns2)                                  # catalog
assert len(ns2["features"]) == 72 and calls["catalog"] >= 2
exec(c2[5], ns2)                                  # results_df + csv
assert Path("all_images_sentinel.csv").exists() and ns2["results_df"]["date"].nunique() == 72
ns2["STEP"] = 5                                   # keep the test small, same logic
exec(c2[6], ns2)                                  # download
files = sorted(Path("planet_downloads").glob("*.tif"))
expected = dates[::5] + ([dates[-1]] if dates[-1] not in dates[::5] else [])
assert [f.stem[-10:] for f in files] == sorted(expected), (len(files), len(expected))
n_calls = len(calls["process"])
exec(c2[6], ns2)                                  # rerun: everything skipped
assert len(calls["process"]) == n_calls
print(f"notebook 2 OK: catalog paging + 404 fallback, {len(files)} dates downloaded, rerun skips existing")

# composites
exec(c2[7], ns2)
comp = {p.name: p for p in Path("composites").glob("*.tif")}
assert sorted(comp) == ["composite_2021.tif", "composite_2022.tif", "composite_2023.tif", "composite_All_years.tif"], comp


def reference(paths):
    stack = []
    for p in paths:
        with rasterio.open(p) as s:
            a = s.read()
        stack.append(np.where(a[4] > 0, a[:4], np.nan))
    return np.nanmedian(np.stack(stack), axis=0)


import warnings
warnings.simplefilter("ignore")
usable = ns2["usable"]
assert Path("planet_downloads/ARPS_Para_2022-04-03.tif") not in usable        # low-coverage date excluded
for name, path in comp.items():
    sel = usable if "All" in name else [p for p in usable if ns2["year_of"](p) == name[10:14]]
    want = reference(sel)
    with rasterio.open(path) as s:
        got = s.read()
        assert s.count == 4 and s.dtypes[0] == "float32" and s.descriptions == ("blue", "green", "red", "nir"), (s.count, s.descriptions)
        assert s.nodata is None or np.isnan(s.nodata)
    assert np.allclose(got, want, equal_nan=True), name
    print(f"  {name}: median of {len(sel)} dates matches independent numpy median")
assert not list(Path("composites").glob("*.tmp.tif"))
mtimes = {n: p.stat().st_mtime_ns for n, p in comp.items()}
exec(c2[7], ns2)
assert mtimes == {n: p.stat().st_mtime_ns for n, p in comp.items()}, "existing composites were rewritten"
print("notebook 2 OK: composites correct, existing ones never overwritten")

# stop on 401
import shutil; shutil.rmtree("planet_downloads")
requests.post = lambda url, **kw: post2(url, **kw) if "process" not in url else Resp(401, text="denied")
exec(c2[6], ns2)
assert not list(Path("planet_downloads").glob("*.tif")) and len(ns2["failed"]) == 1
print("notebook 2 OK: HTTP 401 stops the download after one request")
