"""Pará Forest Change Explorer - Streamlit app.

Run:  streamlit run app.py
Data: read from the notebooks' folders (../composites, ../planet_downloads, ../all_images_sentinel.csv).
      The first launch builds the analysis-ready files into data/processed (about a minute); later launches reuse them.
      Re-run manually with:  python -m para_explorer.precompute
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from para_explorer import config as C  # noqa: E402
from para_explorer import counts as N  # noqa: E402
from para_explorer import globe, store  # noqa: E402
from para_explorer import services as S  # noqa: E402
from para_explorer import theme as T  # noqa: E402
from para_explorer.views import (about_tab, change_tab, composites_tab, copernicus_tab, overview,  # noqa: E402
                                 patches_tab, planet_tab)

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
    st.error(f"No analysis-ready data in **{folder}** ({store.status(folder)['reason']}). Expected the composites of "
             f"notebook 3 in `{raw}`; run `python -m para_explorer.precompute --composites <folder>` or set `PARA_COMPOSITES_DIR`.")
    st.stop()


# ---------------------------------------------------------------------------------- sidebar --
def sidebar() -> SimpleNamespace:
    x = SimpleNamespace()
    with st.sidebar:
        st.markdown("### 🛰️ Explorer")
        x.folder = str(Path(st.text_input("Analysis-ready data folder", value=str(C.PROCESSED_DIR), help="Output of para_explorer.precompute")).expanduser())
        _ensure_data(Path(x.folder))
        x.mtime = S.stamp(x.folder)
        d = S.load_data(x.folder, x.mtime)
        years = [y for y in C.YEARS if y in d["ndvis"]]

        st.markdown("##### Composite & layer")
        x.period = st.radio("Composite", [p for p in C.COMPOSITES if p in d["ndvis"]], horizontal=True)
        x.layer = st.selectbox("Map layer", ["True colour", "NDVI", "NDVI change", "Trajectory", "None"])
        x.show_patches = st.toggle("Show decline patches", value=True)

        st.markdown("##### Change analysis")
        c1, c2 = st.columns(2)
        x.a = c1.selectbox("From", years, index=0)
        x.b = c2.selectbox("To", years, index=len(years) - 1)
        if x.a >= x.b:
            st.warning("Pick a 'To' year later than 'From'.")
            st.stop()
        x.t_moderate, x.t_strong = st.slider("NDVI change thresholds (moderate, strong)", 0.02, 0.60, (C.DEFAULT_T_MODERATE, C.DEFAULT_T_STRONG), 0.01,
                                             help="|ΔNDVI| classes for the change budget; the strong threshold also defines decline patches.")
        x.min_ha = st.slider("Minimum patch size (ha)", 0.25, 20.0, C.DEFAULT_MIN_PATCH_HA, 0.25)
        x.min_rob = st.slider("Minimum patch robustness", 0.0, 1.0, 0.0, 0.2, help="Share of thresholds 0.10-0.30 at which the patch stays flagged.")
        x.hide_recovering = st.checkbox("Hide patches mostly recovering in 2022→23 (>50 %)", value=False)

        st.markdown("##### Map")
        x.basemap = st.selectbox("Basemap", list(globe.BASEMAPS))
        x.opacity = st.slider("Overlay opacity", 0, 100, 85)
        x.intro_wanted = st.toggle("Start with a rotating globe", value=True)
        if st.button("Replay globe intro"):
            st.session_state["intro_done"] = False

        st.markdown("##### Planet Data API")
        x.planet_key = st.text_input("Planet API key", type="password", key="planet_key", placeholder="PL…",
                                     help="Used only for this session to query api.planet.com. Never stored or logged.")
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
    ctx.ndvis, ctx.bounds = d["ndvis"], d["bounds"]
    ctx.period_stats = S.period_stats(ctx.folder, ctx.mtime)

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


main()
