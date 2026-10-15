"""Pará Forest Change Explorer - Streamlit app.

Run:  streamlit run app.py
Data: read from the notebooks' folders (../composites, ../planet_downloads, ../all_images_sentinel.csv).
      The first launch builds the analysis-ready files into data/processed (about a minute); later launches reuse them.
      Re-run manually with:  python -m para_explorer.precompute
"""
from __future__ import annotations

import sys
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from para_explorer import config as C  # noqa: E402
from para_explorer import counts as N  # noqa: E402
from para_explorer import aoi as AOI  # noqa: E402
from para_explorer import credentials, globe, store  # noqa: E402
from para_explorer import services as S  # noqa: E402
from para_explorer import theme as T  # noqa: E402
from para_explorer.views import (about_tab, change_tab, compare, composites_tab, copernicus_tab, downloads, intro,  # noqa: E402
                                 overview, patches_tab, planet_tab)

st.set_page_config(page_title="Pará Forest Change Explorer", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")
st.markdown(T.CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------------------ data folder --
def _ensure_data(folder: Path) -> None:
    """Make sure ``folder`` holds analysis-ready files; build them from the notebooks' composites if not."""
    if store.status(folder)["ok"]:
        return
    raw = C.RAW_COMPOSITES_DIR
    if folder.resolve() == C.PROCESSED_DIR.resolve() and any(raw.glob("composite_*.tif")):
        from para_explorer import precompute
        with st.spinner(f"First launch: preparing NDVI and previews from {raw} (≈1 min, once)…"):
            precompute.run(raw, folder, C.DOWNLOADS_DIR if C.DOWNLOADS_DIR.is_dir() else None,
                           catalog_csv=C.CATALOG_CSV, log=lambda *_: None)
        if store.status(folder)["ok"]:
            return
    st.error("The analysis-ready data could not be prepared. Place the composites of notebook 3 (`composite_<year>.tif`) in the "
             "project's `composites/` folder (or set `PARA_COMPOSITES_DIR`) and run `python -m para_explorer.precompute`.")
    st.stop()


def _side_section(title: str, desc: str) -> None:
    """Sidebar section title with a one-line description of what the controls below change."""
    st.markdown(f'<div class="pe-side-sec">{title}</div><div class="pe-side-desc">{desc}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------------- sidebar --
def sidebar() -> SimpleNamespace:
    x = SimpleNamespace()
    with st.sidebar:
        st.markdown('<div class="pe-side-brand"><div class="pe-logo"></div><div class="pe-side-title">Pará Forest Change Explorer</div></div>'
                    '<div class="pe-side-tag">Vegetation change from satellite imagery · 2021-2023</div>', unsafe_allow_html=True)
        x.folder = str(C.PROCESSED_DIR)            # implementation detail - never shown to the user
        _ensure_data(Path(x.folder))
        x.mtime = S.stamp(x.folder)
        d = S.load_data(x.folder, x.mtime)
        years = [y for y in C.YEARS if y in d["ndvis"]]

        _side_section("🗺️ Map layer", "Choose <b>which period</b> and <b>which data</b> is painted on the globe. "
                      "Patches are the outlined areas of strong decline.")
        x.period = st.radio("Composite", [p for p in C.COMPOSITES if p in d["ndvis"]], horizontal=True)
        x.layer = st.selectbox("Map layer", ["True colour", "NDVI", "NDVI change", "Trajectory", "None"])
        x.show_patches = st.toggle("Show decline patches", value=True)

        _side_section("📉 Change analysis", "Pick the two years to compare and how strict “decline” is. "
                      "Updates the <b>change map, KPIs, charts and patches</b>.")
        c1, c2 = st.columns(2)
        x.a = c1.selectbox("From", years, index=0)
        x.b = c2.selectbox("To", years, index=len(years) - 1)
        if x.a >= x.b:
            st.warning("Pick a 'To' year later than 'From'.")
            st.stop()
        tm, ts = st.slider(f"NDVI change thresholds (moderate, strong) · {C.NDVI_T_MIN:.2f}-{C.NDVI_T_MAX:.2f}",
                           C.NDVI_T_MIN, C.NDVI_T_MAX, (C.DEFAULT_T_MODERATE, C.DEFAULT_T_STRONG), C.NDVI_T_STEP, key="ndvi_thresholds",
                           help="|ΔNDVI| classes for decreases and increases alike; the strong threshold also defines decline patches. "
                                "The range is limited to values the analysis is validated for.")
        x.t_moderate, x.t_strong, warns = C.validate_thresholds(tm, ts)
        for w in warns:
            st.warning(w)
        _side_section("🔍 Decline patches", "Filter which patches are <b>outlined on the map</b> and listed in the Decline patches tab.")
        x.min_ha = st.slider("Minimum patch size (ha)", 0.25, 50.0, C.DEFAULT_MIN_PATCH_HA, 0.25, key="min_patch_ha",
                             help="Larger values keep only bigger patches; if none qualify the app simply shows an empty result.")
        x.min_rob = st.slider("Minimum patch robustness", 0.0, 1.0, 0.0, 0.2, help="Share of thresholds 0.10-0.30 at which the patch stays flagged.")
        x.hide_recovering = st.checkbox("Hide patches mostly recovering in 2022→23 (>50 %)", value=False)

        _side_section("🎛️ Map display", "Background map, layer transparency and the opening animation. "
                      "Does <b>not</b> change any numbers.")
        x.basemap = st.selectbox("Basemap", list(globe.BASEMAPS))
        x.opacity = st.slider("Overlay opacity (%)", 0, 100, 85, 5, key="overlay_opacity", help="Applies to the selected map layer on the globe.")
        x.intro_wanted = st.toggle("Start with a rotating globe", value=True)
        if st.button("Replay globe intro"):
            st.session_state["intro_done"] = False

        _side_section("🛰️ Planet imagery search", "Searches Planet’s catalogue for the Planet imagery tab; matching "
                      "<b>scene footprints appear on the map</b>. Needs your API key.")
        env_key = credentials.get_secret("PLANET_API_KEY")
        typed = st.text_input("Planet API key", type="password", key="planet_key", placeholder="PL… (or set PLANET_API_KEY)",
                              help="Used only for this session to query api.planet.com. Never displayed, stored or logged. "
                                   "For deployments set PLANET_API_KEY as environment variable or Streamlit secret.")
        x.planet_key = typed or env_key
        if env_key and not typed:
            st.caption("🔒 Using the key from the server configuration.")
        up_aoi = st.file_uploader("Area of interest (GeoJSON, optional)", type=["geojson", "json"],
                                  help="Default: the Pará study area. A smaller Polygon/MultiPolygon in lon/lat is used for Planet and Copernicus searches.")
        x.aoi_geometry, x.aoi_label = None, C.AOI_NAME
        if up_aoi is not None:
            geom, err = AOI.parse_geojson(up_aoi.getvalue())
            if err:
                st.error(err)
            else:
                x.aoi_geometry, x.aoi_label = geom, "uploaded area"
        x.cloud = st.slider("Cloud cover (%)", 0, 100, (0, 30), 5)
        dr = st.date_input("Acquisition dates", value=(date(2021, 1, 1), date(2023, 12, 31)), min_value=date(2016, 1, 1), max_value=date.today())
        x.p_start_date, x.p_end_date = (dr[0], dr[1]) if isinstance(dr, (tuple, list)) and len(dr) == 2 else (date(2021, 1, 1), date(2023, 12, 31))
        x.p_start, x.p_end = str(x.p_start_date), str(x.p_end_date)
        x.item_types = st.multiselect("Item types", list(C.PLANET_ALL_ITEM_TYPES), default=list(C.PLANET_DEFAULT_ITEM_TYPES)) or list(C.PLANET_DEFAULT_ITEM_TYPES)
        x.curated_only = st.checkbox(f"Only the {len(C.CURATED_SCENE_IDS)} curated scene IDs of the task", value=False)
        x.max_pages = st.select_slider("Max. scenes to list", [1, 2, 4, 8], value=4, format_func=lambda p: f"{p * 250:,}")
        up = st.file_uploader("…or CSV from notebook 1 (stats only)", type="csv", help="all_images_values.csv: id, acquired, cloud_percent")
        x.csv_df = None
        if up is not None:
            try:
                df = pd.read_csv(up)
                df["acquired"] = pd.to_datetime(df["acquired"], utc=True)
                x.csv_df = df
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read the CSV: {e}")
        st.caption("Imagery is never downloaded: previews are streamed via the API with your key.")
    return x


# ------------------------------------------------------------------------------------ main --
def main() -> None:
    ctx = sidebar()
    d = S.load_data(ctx.folder, ctx.mtime)
    ctx.ndvis, ctx.bounds, ctx.shape = d["ndvis"], d["bounds"], d["shape"]
    ctx.period_stats = S.period_stats(ctx.folder, ctx.mtime)

    ctx.aoi_json = json.dumps(ctx.aoi_geometry) if ctx.aoi_geometry else ""
    ctx.counts_path = Path(ctx.folder) / "composite_counts.json"
    rec = N.load(ctx.counts_path)
    if rec is None and C.DOWNLOADS_DIR.is_dir() and Path(ctx.folder).resolve() == C.PROCESSED_DIR.resolve():
        bar = st.progress(0.0, text="Counting the downloaded images (once)…")
        rec = N.resolve(ctx.folder, C.DOWNLOADS_DIR, C.CATALOG_CSV, progress=lambda i, n: bar.progress(i / n))
        bar.empty()
    ctx.counts = rec["counts"] if rec else {}
    ctx.counts_source = rec["source"] if rec else "not available yet"

    ctx.budget = S.budget(ctx.folder, ctx.mtime, ctx.a, ctx.b, ctx.t_moderate, ctx.t_strong)
    pdf, gj, ctx.patch_summary = S.patches(ctx.folder, ctx.mtime, ctx.a, ctx.b, ctx.t_strong, ctx.min_ha)
    if not pdf.empty:
        keep = pdf["robustness"] >= ctx.min_rob - 1e-9
        if ctx.hide_recovering and "recovering_22_23_pct" in pdf:
            keep &= pdf["recovering_22_23_pct"] <= 50
        pdf = pdf[keep].reset_index(drop=True)
        ids = set(pdf["patch_id"])
        gj = {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["properties"]["patch_id"] in ids]}
    ctx.patch_df, ctx.patch_gj = pdf, gj
    ctx.sel_patch = patches_tab.selected_row(pdf) if not pdf.empty else None

    pl = planet_tab.compute(ctx)           # before the globe: footprints/filters feed the map

    ctx.intro = ctx.intro_wanted and not st.session_state.get("intro_done", False)
    overview.header(ctx)
    intro.user_story()
    intro.basics()
    st.write("")
    overview.kpis(ctx)
    st.write("")
    overview.globe_and_panel(ctx, pl)
    st.session_state["intro_done"] = True
    st.write("")

    tabs = st.tabs(["📦 Composites & image counts", "📈 NDVI change", "🔍 Decline patches", "🛰️ Planet imagery (API)",
                    "🇪🇺 Copernicus context", "ℹ️ Method & limits"])
    with tabs[0]:
        composites_tab.render(ctx)
    with tabs[1]:
        change_tab.render(ctx)
    with tabs[2]:
        patches_tab.render(ctx)
    with tabs[3]:
        planet_tab.render(ctx, pl)
    with tabs[4]:
        copernicus_tab.render(ctx)
    with tabs[5]:
        about_tab.render(ctx)

    st.write("")
    downloads.render(ctx)
    st.write("")
    compare.render(ctx)


main()
