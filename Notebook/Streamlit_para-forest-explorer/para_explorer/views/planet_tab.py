"""Tab: Planet Data API imagery - previews streamed on demand + availability statistics.

Imagery is *discovery only*: we show thumbnails fetched through the API with the user's own key.
There is deliberately no download button for imagery; thumbnails live in server memory for the
session only. Counts for the charts come from the server-side Stats API (see ``planet.py``).
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from para_explorer import compat

from .. import config as C
from .. import planet
from .. import services as S
from .. import theme as T

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MAX_FOOTPRINTS = 400


# ------------------------------------------------------------------------------ compute -----
def compute(ctx) -> SimpleNamespace:
    """Runs *before* the globe is drawn so footprints and filters affect the map. Never raises."""
    s = SimpleNamespace(status="idle", error=None, source=None, monthly=None, scenes=None, truncated=False,
                        total=None, fc=None, highlight=None, focus_year="All")
    key = ctx.planet_key.strip()
    s.focus_year = st.session_state.get("focus_year", "All")
    start, end = ctx.p_start, ctx.p_end
    if key:
        fp = S.fingerprint(key)
        ids = C.CURATED_SCENE_IDS if ctx.curated_only else None
        flt = planet.build_filter(start, end, ctx.cloud[0], ctx.cloud[1], ids)
        fs, fe = start, end
        if s.focus_year != "All":
            fs, fe = max(start, f"{s.focus_year}-01-01"), min(end, f"{s.focus_year}-12-31")
        flt_scene = planet.build_filter(fs, fe, ctx.cloud[0], ctx.cloud[1], ids)
        try:
            s.monthly = S.planet_stats(key, fp, tuple(ctx.item_types), json.dumps(flt), "month")
            feats, s.truncated = S.planet_search(key, fp, tuple(ctx.item_types), json.dumps(flt_scene), "acquired desc", ctx.max_pages)
            s.scenes = planet.to_frame(feats)
            s.status, s.source = "ok", "Planet Data API (Stats + quick-search)"
        except planet.PlanetError as e:
            s.status, s.error = "error", str(e)
    elif ctx.csv_df is not None:
        df = ctx.csv_df.copy()
        a = pd.Timestamp(start, tz="UTC"); b = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        df = df[(df["acquired"] >= a) & (df["acquired"] < b) & df["cloud_percent"].between(*ctx.cloud)]
        s.monthly = planet.monthly_from_frame(df)
        s.scenes = df.assign(year=df["acquired"].dt.year, month=df["acquired"].dt.month, thumbnail=None, geometry=None)
        s.status, s.source = "csv", "uploaded CSV (no thumbnails)"
    if s.monthly is not None and not s.monthly.empty:
        s.total = int(s.monthly["count"].sum())
    elif s.monthly is not None:
        s.total = 0
    sc = s.scenes
    if sc is not None and not sc.empty and "geometry" in sc and sc["geometry"].notna().any():
        feats = [{"type": "Feature", "geometry": g, "properties": {"id": i, "cloud": None if pd.isna(c) else float(c),
                  "acquired": str(a)[:10]}} for i, c, a, g in zip(sc["id"], sc["cloud_percent"], sc["acquired"], sc["geometry"])
                 if g][:MAX_FOOTPRINTS]
        s.fc = {"type": "FeatureCollection", "features": feats}
    pick = st.session_state.get("scene_pick")
    s.highlight = pick if pick and sc is not None and pick in set(sc["id"]) else None
    return s


# ------------------------------------------------------------------------------- charts -----
def _style(fig, title, h=300, **kw):
    fig.update_layout(**T.plotly_layout(h, title=dict(text=title, font=dict(size=14, color=T.TEXT)), showlegend=False, **kw))
    return fig


def _on_year_click():
    try:
        pts = st.session_state["pl_year"]["selection"]["points"]
        if pts:
            st.session_state["focus_year"] = str(int(pts[0]["x"]))
    except (KeyError, TypeError, ValueError):
        pass


def _charts(ctx, pl) -> None:
    m = pl.monthly
    if m is None or m.empty:
        st.info("No scenes match the current filters. Widen the date range or the cloud-cover range.")
        return
    yearly = m.groupby(m["start"].dt.year)["count"].sum().reset_index()
    seas = m.groupby(m["start"].dt.month)["count"].sum().reindex(range(1, 13), fill_value=0)
    c1, c2, c3 = st.columns([1.6, 1, 1.1], gap="large")
    with c1:
        fig = go.Figure(go.Bar(x=m["start"].dt.strftime("%Y-%m-01"), y=m["count"], marker_color="#3987e5",
                               hovertemplate="%{x|%b %Y}: %{y:,} scenes<extra></extra>"))
        compat.plotly_chart(_style(fig, "Available scenes per month", yaxis=dict(gridcolor=T.GRID, title="scenes"),
                               xaxis=dict(type="date", gridcolor=T.GRID)))
    with c2:
        cols = ["#3987e5" if (pl.focus_year in ("All", str(y))) else "#2a3f63" for y in yearly["start"]]
        fig = go.Figure(go.Bar(x=yearly["start"].astype(str), y=yearly["count"], marker_color=cols, text=[f"{v:,}" for v in yearly["count"]],
                               textposition="outside", textfont=dict(color=T.TEXT), cliponaxis=False,
                               hovertemplate="%{x}: %{y:,} scenes<extra></extra>"))
        compat.plotly_chart(_style(fig, "Scenes per year · click a bar to focus", xaxis=dict(type="category"), yaxis=dict(gridcolor=T.GRID, title="scenes")), on_select=_on_year_click, selection_mode="points", key="pl_year")
    with c3:
        fig = go.Figure(go.Bar(x=MONTH_NAMES, y=seas.values, marker_color="#199e70", hovertemplate="%{x}: %{y:,} scenes<extra></extra>"))
        compat.plotly_chart(_style(fig, "Seasonality: scenes per calendar month", yaxis=dict(gridcolor=T.GRID, title="scenes")))


# ------------------------------------------------------------------------------ previews -----
def _fetch_thumbs(key: str, urls: list[str], width: int) -> dict[str, bytes | None]:
    """Fetch missing thumbnails in parallel; memory-only cache in the user's session."""
    cache = st.session_state.setdefault("_thumbs", {})
    fp = S.fingerprint(key)
    todo = [u for u in urls if (fp, u, width) not in cache]

    def one(u):
        try:
            return u, planet.thumbnail(key, u, width)
        except planet.PlanetError:
            return u, None

    if todo:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for u, b in ex.map(one, todo):
                cache[(fp, u, width)] = b
        while len(cache) > 240:
            cache.pop(next(iter(cache)))
    return {u: cache.get((fp, u, width)) for u in urls}


def _previews(ctx, pl) -> None:
    sc = pl.scenes
    if sc is None or sc.empty:
        return
    st.markdown("#### Scene previews")
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.4])
    sort = c1.selectbox("Sort by", ["Most recent", "Oldest", "Clearest first"], key="sort_by")
    per = c2.selectbox("Per page", [8, 12, 24], index=1, key="per_page")
    sc = {"Most recent": sc.sort_values("acquired", ascending=False), "Oldest": sc.sort_values("acquired"),
          "Clearest first": sc.sort_values(["cloud_percent", "acquired"], ascending=[True, False])}[sort].reset_index(drop=True)
    pages = max(1, -(-len(sc) // per))
    page = c3.number_input("Page", 1, pages, 1, key="page")
    sub = sc.iloc[(page - 1) * per: page * per]
    c4.selectbox("Highlight on globe", ["-"] + sub["id"].tolist(), key="scene_pick_box",
                 on_change=lambda: st.session_state.__setitem__("scene_pick", None if st.session_state["scene_pick_box"] == "-" else st.session_state["scene_pick_box"]))
    msg = f"Showing {len(sub)} of {len(sc):,} loaded scenes"
    if pl.total is not None:
        msg += f" · {pl.total:,} match the filters in total"
    if pl.truncated:
        msg += f" · list capped at {ctx.max_pages * 250:,} newest scenes (charts use the full server-side count)"
    st.caption(msg)

    if pl.status == "csv":
        st.info("Previews need the live API: enter your Planet API key in the sidebar. Statistics above come from your uploaded CSV.")
        compat.dataframe(sub[["id", "acquired", "cloud_percent", "quality"]] if "quality" in sub else sub[["id", "acquired", "cloud_percent"]], hide_index=True)
        return
    thumbs = _fetch_thumbs(ctx.planet_key.strip(), [u for u in sub["thumbnail"] if u], 512)
    cols = st.columns(4)
    for i, (_, r) in enumerate(sub.iterrows()):
        with cols[i % 4]:
            data = thumbs.get(r["thumbnail"])
            if data:
                compat.image(data)
            else:
                st.markdown('<div class="pe-card pe-note" style="height:120px;display:flex;align-items:center;justify-content:center">preview unavailable</div>', unsafe_allow_html=True)
            cloud = "n/a" if pd.isna(r["cloud_percent"]) else f"{r['cloud_percent']:.0f} %"
            st.markdown(f'<div class="pe-scene-cap"><b>{r["acquired"]:%Y-%m-%d %H:%M} UTC</b><br>{r["id"]}<br>{r["item_type"]} · cloud {cloud}</div>', unsafe_allow_html=True)
    with st.expander("All loaded scenes (table)"):
        compat.dataframe(sc.drop(columns=["geometry", "thumbnail"], errors="ignore"), hide_index=True)


# ------------------------------------------------------------------------------- render -----
def render(ctx, pl) -> None:
    st.markdown("#### Planet imagery through the Data API")
    if pl.status == "idle":
        st.markdown(
            '<div class="pe-card"><h4>Enter your Planet API key to stream imagery</h4>'
            '<div class="pe-note">Planet scenes cannot be downloaded here. Previews are fetched on demand through the Planet Data API '
            'with <b>your own key</b> (sidebar → <i>Planet API key</i>), shown in this session only and never stored. Find the key in your '
            '<a href="https://www.planet.com/account/#/" target="_blank">Planet account</a> under <i>My settings</i>. '
            'You can then filter by <b>cloud cover</b> and <b>dates</b> and see how many scenes exist per month and year. '
            'No key at hand? Upload the <code>all_images_values.csv</code> from notebook 1 in the sidebar to explore the statistics offline.</div></div>',
            unsafe_allow_html=True)
        return
    if pl.status == "error":
        st.error(pl.error)
        return
    # keep the focus-year control in sync with the years present
    years = sorted({int(y) for y in pl.monthly["start"].dt.year}) if pl.monthly is not None and not pl.monthly.empty else []
    opts = ["All"] + [str(y) for y in years]
    if st.session_state.get("focus_year", "All") not in opts:
        st.session_state["focus_year"] = "All"
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(T.kpi("Scenes matching filters", f"{pl.total:,}" if pl.total is not None else "-", pl.source or ""), unsafe_allow_html=True)
    k2.markdown(T.kpi("Date range", f"{ctx.p_start[:7]} → {ctx.p_end[:7]}", f"{', '.join(ctx.item_types)}"), unsafe_allow_html=True)
    k3.markdown(T.kpi("Cloud cover", f"{ctx.cloud[0]}-{ctx.cloud[1]} %", "field cloud_percent"), unsafe_allow_html=True)
    sc = pl.scenes
    med = f"{sc['cloud_percent'].median():.0f} %" if sc is not None and not sc.empty and sc["cloud_percent"].notna().any() else "n/a"
    k4.markdown(T.kpi("Median cloud (loaded)", med, f"{len(sc):,} scenes loaded" if sc is not None else ""), unsafe_allow_html=True)
    st.write("")
    top = st.columns([1, 3])
    top[0].selectbox("Focus year (also: click a bar)", opts, key="focus_year")
    top[1].markdown('<div class="pe-note" style="padding-top:28px">The focus year filters the previews and the footprints on the globe; charts keep showing the whole range.</div>', unsafe_allow_html=True)
    _charts(ctx, pl)
    _previews(ctx, pl)
