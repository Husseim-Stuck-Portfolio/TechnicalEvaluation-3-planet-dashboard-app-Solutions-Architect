"""Tab: the yearly composites and how many images went into each of them."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from para_explorer import compat

from .. import config as C
from .. import counts as N
from .. import services as S
from .. import theme as T

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _count_charts(ctx) -> None:
    counts = ctx.counts
    c1, c2 = st.columns([1, 1.35], gap="large")
    with c1:
        names = [p for p in C.COMPOSITES if p in counts]
        vals = [counts[p]["items"] for p in names]
        fig = go.Figure(go.Bar(x=names, y=vals, name="downloaded", marker_color=[T.PERIOD_COLORS[p] for p in names], text=vals,
                               textposition="outside", textfont=dict(color=T.TEXT), cliponaxis=False,
                               hovertemplate="%{x}: %{y} images downloaded<extra></extra>"))
        top = max(vals + [1])
        if all(counts[p].get("usable") is not None for p in names):
            us = [counts[p]["usable"] for p in names]
            fig.add_trace(go.Bar(x=names, y=us, name="≥50 % valid pixels", marker_color="rgba(255,255,255,0.28)",
                                 hovertemplate="%{x}: %{y} with ≥50 % valid pixels<extra></extra>"))
        if all(counts[p].get("available") is not None for p in names):
            av = [counts[p]["available"] for p in names]
            top = max(top, *av)
            fig.add_trace(go.Scatter(x=names, y=av, mode="markers", name="in catalog (available)",
                                     marker=dict(symbol="line-ew", size=26, line=dict(width=3, color=T.ACCENT)),
                                     hovertemplate="%{x}: %{y} images in catalog<extra></extra>"))
        fig.update_layout(**T.plotly_layout(330, title=dict(text="Images per composite", font=dict(size=14, color=T.TEXT)),
                                            barmode="overlay", showlegend=True,
                                            yaxis=dict(gridcolor=T.GRID, title="images", range=[0, top * 1.18])))
        compat.plotly_chart(fig)
    with c2:
        have = [y for y in C.YEARS if counts.get(y, {}).get("monthly")]
        if have:
            fig = go.Figure()
            for y in have:
                m = counts[y]["monthly"]
                fig.add_bar(x=MONTHS, y=[m[f"{k:02d}"] for k in range(1, 13)], name=y, marker_color=T.PERIOD_COLORS[y],
                            hovertemplate=f"{y} %{{x}}: %{{y}} images<extra></extra>")
            fig.update_layout(**T.plotly_layout(330, title=dict(text="Images per month, by year", font=dict(size=14, color=T.TEXT)),
                                                barmode="group", bargap=0.25, yaxis=dict(gridcolor=T.GRID, title="images")))
            compat.plotly_chart(fig)
        else:
            st.info("Monthly breakdown is available when counts come from the Sentinel Hub Catalog API or the "
                    "download folder (they carry acquisition dates).")
    tbl = [{"composite": p, "images downloaded": counts[p]["items"], "≥50 % valid pixels": counts[p].get("usable"),
            "in catalog": counts[p].get("available"), "acquisition dates": counts[p].get("dates")}
           for p in C.COMPOSITES if p in counts]
    compat.dataframe(tbl, hide_index=True)


def _count_setup(ctx) -> None:
    with st.expander("Image counts: source, refresh, or enter manually", expanded=not ctx.counts):
        st.caption(f"Current source: **{ctx.counts_source}**. “images downloaded” = the per-date GeoTIFFs of "
                   "notebook 2 (what a per-image median iterates over); “≥50 % valid pixels” = those with usable data over the AOI; "
                   "“in catalog” = all items the catalog lists for the AOI; “acquisition dates” = distinct days.")
        a, b = st.columns(2)
        with a:
            st.markdown("**Count via Sentinel Hub Catalog API** (OAuth client from the Planet account app)")
            cid = st.text_input("Client ID", key="sh_id", type="password")
            sec = st.text_input("Client secret", key="sh_secret", type="password")
            if st.button("Search catalog for 2021, 2022, 2023", disabled=not (cid and sec)):
                try:
                    with st.spinner("Searching the sandbox collection…"):
                        rec = N.from_sentinel_hub(cid, sec)
                    N.save(rec, ctx.counts_path)
                    st.rerun()
                except Exception as e:  # noqa: BLE001 - show any failure to the user, never crash the app
                    st.error(f"Catalog search failed: {e}")
        with b:
            st.markdown("**…or type the numbers** (e.g. from notebook 2)")
            vals = {y: st.number_input(f"Images in {y}", min_value=0, step=1, key=f"man_{y}") for y in C.YEARS}
            if st.button("Save manual counts"):
                N.save(N.manual(vals), ctx.counts_path)
                st.rerun()


def _grid(ctx, mode: str) -> None:
    """2 x 2 grid of identical square images (never stretched); wraps to one column on narrow screens."""
    kind = "rgb" if mode == "True colour" else "ndvi"
    periods = [p for p in C.COMPOSITES if p in ctx.ndvis]
    for row in range(0, len(periods), 2):
        cols = st.columns(2, gap="medium")
        for col, p in zip(cols, periods[row:row + 2]):
            n = ctx.counts.get(p, {}).get("items") if ctx.counts else None
            sub = f"{n} images downloaded" if n is not None else ""
            png = S.composite_png(ctx.folder, ctx.mtime, p, kind, "dark", sub)
            with col:
                compat.image(png)
                st.download_button(f"⬇ {p} · {mode.lower()} (PNG)", S.composite_png(ctx.folder, ctx.mtime, p, kind, "light", sub),
                                   file_name=f"composite_{p.replace(' ', '_')}_{kind}.png", mime="image/png", key=f"dl_grid_{kind}_{p}")


def render(ctx) -> None:
    st.markdown("#### How many images composed each year?")
    if ctx.counts:
        _count_charts(ctx)
    else:
        st.warning("No image counts yet for these composites. Use the panel below to count them from the Sentinel "
                   "Hub Catalog API or to type them in.")
    _count_setup(ctx)
    st.markdown("#### The yearly composites side by side")
    _grid(ctx, st.radio("Show", ["True colour", "NDVI"], horizontal=True, key="grid_mode"))
    st.caption("NDVI is a ratio and does not depend on the reflectance scale. All composites share one pixel grid, so "
               "differences between panels are differences in the composited imagery, not in alignment.")
