"""Section: Planet vs Copernicus - same area, comparable period, side by side."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from para_explorer import compat

from .. import config as C
from .. import copernicus_imagery as CI
from .. import credentials
from .. import figures as F
from .. import services as S

CHECKLIST = pd.DataFrame([
    ("Location", "Same bounding box of the study area; both images are requested/cut on identical coordinates."),
    ("Date or season", "Planet composite = all downloaded scenes of the period; Copernicus = median of cloud-masked scenes in the same window. "
                       "Different acquisition days and seasonal sampling can still differ."),
    ("Cloud and haze", "Copernicus clouds are masked with the Sentinel-2 scene classification; Planet composites rely on the sandbox quality mask."),
    ("Spatial resolution", "Planet composite grid ≈10 m (source ≈3 m) vs Sentinel-2 10 m; both are resampled to one common grid here."),
    ("Projection", "Both in EPSG:4326 (WGS 84)."),
    ("Band definitions", "Different sensors have different spectral response in red and NIR, so NDVI values are not identical."),
    ("Preprocessing", "Different atmospheric correction and compositing methods. Treat the comparison as an independent plausibility check, not a one-to-one measurement."),
], columns=["Must be aligned", "Status in this app"])


def interpretation(period: str, m: dict, t: pd.DataFrame, cop_ok: bool) -> str:
    if not cop_ok:
        return ("Load the Copernicus image to see how the two datasets agree. Until then only the Planet column is filled; "
                "no conclusion about agreement can be drawn.")
    pm, cm = float(t.loc[0, "Planet"]), float(t.loc[0, "Copernicus"])
    diff = pm - cm
    r = m.get("r", np.nan)
    if not np.isfinite(r):
        agree = "There are too few overlapping valid pixels to judge the agreement."
    elif r >= 0.8:
        agree = f"Spatial patterns agree strongly (pixel correlation r = {r:.2f})."
    elif r >= 0.5:
        agree = f"Spatial patterns agree moderately (r = {r:.2f}); some differences come from timing, clouds or sensor response."
    else:
        agree = f"Spatial patterns agree only weakly (r = {r:.2f}); check dates, clouds and masks before trusting either dataset."
    return (f"For {period}, mean NDVI is {pm:.3f} from Planet and {cm:.3f} from Copernicus (Planet − Copernicus = {diff:+.3f}). {agree} "
            "Dense tropical forest saturates NDVI near 0.8-0.9, so small differences are expected and the minimum/maximum are sensitive to "
            "single pixels. Because the datasets differ in dates, processing and sensor response, this is a plausibility check - "
            "not a one-to-one measurement - unless the data are harmonised.")


def render(ctx) -> None:
    st.markdown("## Planet vs Copernicus: Same Area Comparison")
    st.markdown("Planet and Copernicus Sentinel-2 views of the **same area** (identical bounding box, one common pixel grid) for a "
                "comparable period. Differences show where the two independent datasets agree - and where dates, clouds or sensors matter.")
    c1, c2 = st.columns([1, 1.3], gap="large")
    with c1:
        period = st.selectbox("Composite to compare", [p for p in C.COMPOSITES if p in ctx.ndvis],
                              index=[p for p in C.COMPOSITES if p in ctx.ndvis].index(ctx.period), key="cmp_period")
        start, end = CI.window_for(period)
        max_cloud = st.slider("Max. scene cloud cover for Copernicus (%)", 10, 100, 70, 10, key="cmp_cloud")
        path = CI.cache_path(ctx.folder, start, end, max_cloud)
    with c2:
        cid_env, sec_env = credentials.cdse_credentials()
        with st.expander("Copernicus credentials (free CDSE OAuth client)", expanded=not path.exists() and not (cid_env and sec_env)):
            st.caption("Create an OAuth client in the Copernicus Data Space dashboard (User settings → OAuth clients). "
                       "Values are kept in this session only; for deployments use CDSE_CLIENT_ID / CDSE_CLIENT_SECRET.")
            cid = st.text_input("Client ID", type="password", key="cdse_cid", value="")
            sec = st.text_input("Client secret", type="password", key="cdse_sec", value="")
        cid, sec = cid or cid_env, sec or sec_env
        go = st.button("Load Copernicus Sentinel-2 image", type="primary", key="cmp_load",
                       help="Requests one cloud-masked median image of the AOI; the result is cached for next time.")
        if path.exists():
            st.caption("✅ A Copernicus image for this period is already stored with the app.")

    if go:
        try:
            with st.spinner("Requesting Sentinel-2 L2A from the Copernicus Data Space Ecosystem… this can take a minute"):
                scene = CI.fetch(cid, sec, start, end, max_cloud)
            if not scene["valid"].any():
                st.warning("Copernicus returned no valid pixels for this window and cloud limit. Try a higher cloud limit.")
            else:
                CI.save(scene, path, {"from": start, "to": end, "max_cloud": max_cloud, "source": "CDSE Sentinel Hub Process API, sentinel-2-l2a"})
                S.copernicus_scene.clear()
        except CI.CopernicusError as e:
            st.error(str(e))

    loaded = S.copernicus_scene(str(path), path.stat().st_mtime if path.exists() else 0.0) if path.exists() else None
    scene = loaded[0] if loaded else None
    p_nd, p_rgb = S.planet_on_grid(ctx.folder, ctx.mtime, period)
    c_nd = CI.ndvi(scene) if scene else None
    c_rgb = CI.rgb(scene) if scene else None
    stac = S.copernicus_stac(start, end, float(max_cloud)) if scene else {}
    cop_dates = f"{start} → {end} window" + (f" · {stac['n']} scenes, {stac['first']} → {stac['last']}" if stac.get("n") else "")
    p_valid = 100 * np.isfinite(p_nd).mean()
    table = CI.table(period, p_nd, p_valid, S.planet_dates(ctx.folder, ctx.mtime, period), c_nd, cop_dates,
                     p_nd.shape, (ctx.shape[0], ctx.shape[1]))
    metrics = CI.compare(p_nd, c_nd) if scene else {}
    text = interpretation(period, metrics, table, scene is not None)

    png = F.to_png(F.comparison_figure(p_rgb, c_rgb, p_nd, c_nd, ("Planet", "Copernicus"), "dark"), dpi=110)
    compat.image(png)
    st.markdown("#### Side-by-side metrics")
    compat.dataframe(table, hide_index=True)
    if metrics and np.isfinite(metrics.get("r", np.nan)):
        k = st.columns(3)
        k[0].metric("Pixel correlation (NDVI)", f"{metrics['r']:.2f}")
        k[1].metric("Mean difference (Planet − Copernicus)", f"{metrics['bias']:+.3f}")
        k[2].metric("RMSE", f"{metrics['rmse']:.3f}")
    st.info("**Interpretation.** " + text)
    with st.expander("When is this comparison valid? (alignment checklist)"):
        compat.dataframe(CHECKLIST, hide_index=True)

    light = F.to_png(F.comparison_figure(p_rgb, c_rgb, p_nd, c_nd, ("Planet", "Copernicus"), "light"), dpi=130)
    st.session_state["cmp_result"] = {"period": period, "png": light, "table": table, "text": text, "metrics": metrics,
                                      "loaded": scene is not None, "cop_png": None}
    if scene:
        cop_png = F.to_png(F.composite_figure("rgb", c_rgb, f"Copernicus Sentinel-2 · {period}", cop_dates, "light"))
        cop_nd_png = F.to_png(F.composite_figure("ndvi", c_nd, f"Copernicus NDVI · {period}", cop_dates, "light"))
        st.session_state["cmp_result"]["cop_png"] = cop_png
        st.session_state["cmp_result"]["cop_ndvi_png"] = cop_nd_png
