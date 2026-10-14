"""Section: everything the analyst can take away - graphs, maps, composite images, CSV statistics and a PDF report."""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from .. import config as C
from .. import report
from .. import services as S


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def statistics_table(ctx) -> pd.DataFrame:
    """One row per composite: NDVI statistics plus the number of images behind it."""
    t = ctx.period_stats.copy()
    n = ctx.counts or {}
    t["images_downloaded"] = [n.get(p, {}).get("items") for p in t["period"]]
    t["images_valid_over_50pct"] = [n.get(p, {}).get("usable") for p in t["period"]]
    t["images_in_catalog"] = [n.get(p, {}).get("available") for p in t["period"]]
    t["acquisition_dates"] = [n.get(p, {}).get("dates") for p in t["period"]]
    return t.round(4)


def counts_table(ctx) -> pd.DataFrame:
    rows = []
    for p in C.COMPOSITES:
        if p not in ctx.ndvis:
            continue
        n = (ctx.counts or {}).get(p, {})
        rows.append((p, S.planet_dates(ctx.folder, ctx.mtime, p), n.get("items", "n/a"), n.get("usable", "n/a"), n.get("available", "n/a")))
    return pd.DataFrame(rows, columns=["Composite", "Acquisition period", "Images downloaded", "≥50 % valid", "In catalog"])


def collect_report(ctx) -> bytes:
    f, m = ctx.folder, ctx.mtime
    comps = {}
    for p in C.COMPOSITES:
        if p in ctx.ndvis:
            sub = ""
            comps[p] = {"rgb": S.composite_png(f, m, p, "rgb", "light", sub), "ndvi": S.composite_png(f, m, p, "ndvi", "light", sub)}
    stats = statistics_table(ctx)[["period", "mean_ndvi", "median_ndvi", "p05", "p95", "valid_km2"]].rename(columns={
        "period": "Composite", "mean_ndvi": "Mean NDVI", "median_ndvi": "Median", "p05": "5th pct", "p95": "95th pct", "valid_km2": "Valid km²"})
    bud = ctx.budget.copy()
    bud["area_ha"] = bud["area_ha"].map("{:,.1f}".format)
    bud["pct_valid"] = bud["pct_valid"].map(lambda v: "-" if pd.isna(v) else f"{v:.2f} %")
    bud = bud.rename(columns={"class": "Class", "pixels": "Pixels", "area_ha": "Area (ha)", "pct_valid": "% of valid"})
    cmp_ = st.session_state.get("cmp_result")
    content = {
        "aoi_png": S.aoi_png(f, m, ctx.a, ctx.b, ctx.t_strong, ctx.min_ha),
        "composites": comps, "counts_df": counts_table(ctx),
        "dist_png": S.ndvi_dist_png(f, m), "change_png": S.change_png(f, m, ctx.a, ctx.b, "light"),
        "budget_png": S.budget_png(f, m, ctx.a, ctx.b, ctx.t_moderate, ctx.t_strong), "hist_png": S.hist_png(f, m, ctx.a, ctx.b, ctx.t_moderate, ctx.t_strong),
        "period_stats_df": stats.round(3), "budget_df": bud,
        "thresholds": {"moderate": ctx.t_moderate, "strong": ctx.t_strong, "from": ctx.a, "to": ctx.b, "min_ha": ctx.min_ha},
        "patch_summary": ctx.patch_summary, "comparison": cmp_,
    }
    return report.build(content)


def render(ctx) -> None:
    st.markdown("## ⬇️ Downloads")
    st.caption("Everything below is generated from the data in this app. Planet API scene previews are intentionally not downloadable; "
               "the yearly composites are your own processed PlanetScope-derived products.")
    f, m = ctx.folder, ctx.mtime
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown("**Graphs and maps**")
        st.download_button("NDVI per year (graph, PNG)", S.ndvi_dist_png(f, m), "ndvi_per_year.png", "image/png", key="dl_dist")
        st.download_button("Change budget (graph, PNG)", S.budget_png(f, m, ctx.a, ctx.b, ctx.t_moderate, ctx.t_strong),
                           f"ndvi_change_budget_{ctx.a}_{ctx.b}.png", "image/png", key="dl_budget")
        st.download_button("NDVI change distribution (PNG)", S.hist_png(f, m, ctx.a, ctx.b, ctx.t_moderate, ctx.t_strong),
                           f"ndvi_change_histogram_{ctx.a}_{ctx.b}.png", "image/png", key="dl_hist")
        st.download_button("NDVI change map (PNG)", S.change_png(f, m, ctx.a, ctx.b, "light"), f"ndvi_change_map_{ctx.a}_{ctx.b}.png",
                           "image/png", key="dl_change")
    with c2:
        st.markdown("**Images**")
        imgs = {}
        for p in C.COMPOSITES:
            if p in ctx.ndvis:
                slug = C.slug(p)
                imgs[f"composite_{slug}_true_colour.png"] = S.composite_png(f, m, p, "rgb", "light", "")
                imgs[f"composite_{slug}_ndvi.png"] = S.composite_png(f, m, p, "ndvi", "light", "")
        st.download_button("Yearly composites (ZIP of PNGs)", _zip(imgs), "yearly_composites.zip", "application/zip", key="dl_zip")
        cmp_ = st.session_state.get("cmp_result")
        if cmp_ and cmp_.get("loaded"):
            st.download_button("Copernicus true colour (PNG)", cmp_["cop_png"], "copernicus_true_colour.png", "image/png", key="dl_cop_rgb")
            st.download_button("Copernicus NDVI (PNG)", cmp_["cop_ndvi_png"], "copernicus_ndvi.png", "image/png", key="dl_cop_ndvi")
            st.download_button("Planet vs Copernicus panel (PNG)", cmp_["png"], "planet_vs_copernicus.png", "image/png", key="dl_cmp")
        else:
            st.caption("Copernicus images become available after you load them in the comparison section below.")
    with c3:
        st.markdown("**Statistics (CSV)**")
        st.download_button("Composite statistics & image counts", statistics_table(ctx).to_csv(index=False), "composite_statistics.csv", "text/csv", key="dl_csv1")
        st.download_button("Change budget", ctx.budget.to_csv(index=False), f"change_budget_{ctx.a}_{ctx.b}.csv", "text/csv", key="dl_csv2")
        st.download_button("Decline patches", ctx.patch_df.drop(columns=["bbox"], errors="ignore").to_csv(index=False),
                           "decline_patches.csv", "text/csv", key="dl_csv3")

    st.markdown("**Complete PDF report**")
    st.caption("Includes the AOI map, data sources, dates, NDVI explanation and formula, thresholds, yearly composites and NDVI graphs, "
               "the change map and statistics, the Planet-vs-Copernicus comparison (if loaded), interpretation, limitations and future work.")
    if st.button("Prepare PDF report", key="pdf_make"):
        try:
            with st.spinner("Building the report…"):
                st.session_state["pdf_bytes"] = collect_report(ctx)
        except Exception as e:  # noqa: BLE001 - never crash the app because a figure failed
            st.session_state.pop("pdf_bytes", None)
            st.error(f"The report could not be created ({type(e).__name__}). Please try again or download the single files above.")
    if st.session_state.get("pdf_bytes"):
        st.download_button("⬇ Download PDF report", st.session_state["pdf_bytes"], "para_forest_change_report.pdf", "application/pdf", key="pdf_dl")
